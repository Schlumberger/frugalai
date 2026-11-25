import json
import sys
import os
import yaml
from flask import Flask, request, render_template, session

# ---------------------------------------------------------
# When run with the default routes.yaml, the app will allow
#  the creation of orchestrated LLM-enabled workflows.
# When run with your custom YAML, the app will execute your
#  custom workflow.
# NOTE: the goal is to only expose the minimum for human
#   interaction with your backend designs.
# ---------------------------------------------------------

from frugal.agents import Client, LLMResponse
from frugal.registry import AgentRegistry
from frugal.routing import create_route, load_routes_from_yaml
from frugal.visitors import VISITOR_REGISTRY
from frugal.resumable_registry import ResumableRegistry
from frugal.resilient_registry import ResilientRegistry
# exceptions
from frugal.agents import TooManyTokens, LLMFailed, WorkflowInterrupt, HumanInputRequired

def safe_serialize(obj):
    # Try common patterns vendors use
    if hasattr(obj, "model_dump"):   # pydantic v2
        return obj.model_dump()
    if hasattr(obj, "dict"):         # pydantic v1
        return obj.dict()
    if hasattr(obj, "__dict__"):
        return obj.__dict__

    # Fallback: stringify
    return str(obj)

def resource_path(relative):
    base = getattr(sys, '_MEIPASS', os.path.abspath("."))
    return os.path.join(base, relative)


# ----------------------------------
# Flask App
# ----------------------------------

app = Flask(
    __name__,
    template_folder=resource_path("templates"),
    static_folder=resource_path("static")
)

app.secret_key = "dev-secret"


# ----------------------------------
# LLM setup
# ----------------------------------

def getLLM():
    if not os.path.exists("./credfile.json"):
        return None

    with open("./credfile.json") as f:
        credentials = json.load(f)

    cfg = credentials["default"]

    provider = cfg.get("provider", "azure")

    if provider == "azure":
        try:
            from openai import AzureOpenAI
        except ImportError:
            return None, False

        return AzureOpenAI(
            api_version=cfg["api_version"],
            azure_endpoint=cfg["endpoint"],
            api_key=cfg["credential"]
        ), False  # no need to stream a

    elif provider == "local-openai":
        # --deployment qwen3.6-colibri
        try:
            from openai import OpenAI
        except ImportError:
            return None

        return OpenAI(
            base_url=cfg["base_url"],
            api_key=cfg.get("api_key", "dummy"),
            timeout = 1800.0
        ), True # stream because local hosting can be slow

    return None, False



# ----------------------------------
# Client with human fallback
# ----------------------------------
class AzureOpenAIClient(Client):
    def __init__(self, client):
        self.client = client[0]
        self.stream = client[1]

    def chat(
        self,
        model=None,
        temperature=None,
        max_tokens=None,
        messages=None
    ):

        if not self.stream:
            response =  self.client.chat.completions.create(
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                messages=messages
                )
            return LLMResponse(
                content=response.choices[0].message.content,
                usage=response.usage)

        print(f"{model=}, {temperature=}, {max_tokens=}")
        stream = self.client.chat.completions.create(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            messages=messages,
            stream=True,
            timeout=3600.0,
        )

        parts = []

        for chunk in stream:
            print(".", end="", flush=True)  # heartbeat

            if not chunk.choices:
                continue

            delta = chunk.choices[0].delta.content

            if delta:
                print(delta, end="", flush=True)
                parts.append(delta)

        print()
        response_text = "".join(parts)
        usage = 0
        return LLMResponse(content="".join(parts),usage=usage)


class FailingClient(Client):
    def chat(self, *args, **kwargs):
        raise RuntimeError("Simulated LLM failure")




ROUTES = None
DECISIONS = {}

# set_routes - expanded to handle routes and decisions
# NOTE: existing cases will run as before with DECISIONS = {}
def set_routes(config_file):
    global ROUTES
    global DECISIONS

    ROUTES = load_routes_from_yaml(config_file)

    with open(config_file, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    DECISIONS = {}

    for d in cfg.get("decisions", []):
        step = d.get("step")
        if step:
            DECISIONS[step] = d

# additional route helper, decisions can access paths
def get_route_by_path(path):
    global ROUTES

    for route in ROUTES:
        if route["path"] == path:
            return route

    return None

###################################################################
# basic UI components for UI tasks
def render_single_select_table(interrupt):
    sid = interrupt["state_id"]
    ui = interrupt["ui_spec"]

    title = ui.get("title", "Select Option")
    paragraph = ui.get("paragraph", "")
    columns = ui.get("columns", [])
    rows = ui.get("rows", [])

    html = f"""
    <h2>{title}</h2>

    <p>{paragraph}</p>

    <form method="POST">

        <input
            type="hidden"
            name="state_id"
            value="{sid}"
        >

        <table border="1">
            <tr>
                <th>Select</th>
    """
    for col in columns:
        html += f"<th>{col}</th>"
    html += "</tr>"

    for i, row in enumerate(rows):
        html += f"""
        <tr>
            <td><input type="radio" name="selected_row" value="{i}" required></td>
        """

        for col in columns:
            html += f"<td>{row.get(col, '')}</td>"

        html += "</tr>"
    html += f"""
        </table>
        <input type="hidden" name="response_json" value="" id="response_json">
        <br>
        <button type="submit">Submit</button>
    </form>

    <script>
    const rows = {json.dumps(rows)};
    document.querySelector("form").addEventListener("submit", function() {{
            const selected = document.querySelector('input[name="selected_row"]:checked');
            if(selected) {{
                document.getElementById("response_json").value =
                    JSON.stringify(rows[parseInt(selected.value)]);
            }}
        }});
    </script>
    """
    return html
    
def render_ui_interrupt(interrupt):
    ui = interrupt["ui_spec"]
    ui_type = ui.get("type")
    if ui_type == "textarea":
        return render_textarea_interrupt(interrupt)

    if ui_type == "single_select_table":
        return render_single_select_table(interrupt)

    return f"""
    <h2>Unknown UI Type</h2>
    <pre>{json.dumps(ui, indent=4)}</pre>
    """


def build_app(app,client,registry,
              deployment = "gpt-4.1"):
    global ROUTES

    # ----------------------------------
    # Routes
    # ----------------------------------

    for route in ROUTES:
        # test whether this route exists...
        agent_dir = route.get("agent_dir",None)
        if not (agent_dir and os.path.isdir(agent_dir) and any(f.is_file() for f in os.scandir(agent_dir))):
            # add URL with error message
            continue

        # The Frugal route
        handler = create_route(
            route,
            registry,
            client,
            deployment,
            VISITOR_REGISTRY
        )

        endpoint_name = route["path"].strip("/").replace("/", "_") or "root"

        def make_flask_handler(route, handler):

            def flask_handler():

                prompt = ""
                state_id = None
                human_response = None
                from_decision = False

                # Handle the case where we arrive from a decision point - no user prompt needed.
                from_decision = ( request.args.get("from_decision", "").lower() == "true")
                if from_decision:
                    prompt = "__CONTINUE__"

                if request.method == "POST":
                    state_id = request.form.get("state_id")
                    # Structured UI response
                    response_json = request.form.get("response_json")
                    if response_json:
                        try:
                            human_response = str(json.loads(response_json)) # test for correct JSON...
                        except Exception:
                            print(f"Expected JSON, attempting to parse as string instead")
                            human_response = response_json
                        print(human_response)
                        prompt = human_response
                    else:
                        # Existing textarea/manual response behaviour
                        human_response = request.form.get( "prompt","")
                        prompt = human_response
                    from_dec = request.form.get("from_decision")
                    print(f"{from_dec=}")
                    if from_dec:
                        from_decision = from_dec

                # ----------------------------------
                # RESUME path
                # ----------------------------------
                if state_id:
                    state = registry.load_state(state_id)
                    state["human_response"] = human_response
                    registry.state = state
                    registry.interrupt = None
                else:
                    registry.state = {"responses": {}}
                    registry.interrupt = None
    
                # instantiate any decision artefacts
                artifacts = session.get("workflow_artifacts",{})
                registry.state["responses"].update(artifacts)
                registry.state["from_decision"] = from_decision

                # RUN ENGINE
                result=None
                try:
                    result = handler(prompt)
                except Exception as ex:
                    if isinstance(ex, TooManyTokens) or isinstance(ex, LLMFailed):
                        # in here we suggest the user restarts with the --use-resumable-registry option
                        print(f"{type(ex).__name__}: Failing due to LLM, consider using the --use-resumable-registry option.")
                    elif isinstance(ex, HumanInputRequired): # must be before its parent exception - the WorkflowInterrupt
                        print("HumanInputRequired: Agent handling incomplete, attempting to interpret in human interface")
                        print(f"Requires the use of the --use-resumable-registry option.")
                    elif isinstance(ex, WorkflowInterrupt):
                        print("WorkflowInterrupt: Agent can't handle case, failing to human prompt interface")
                        print(f"Requires the use of the --use-resumable-registry option.")
                    else:
                        # general exception reporting
                        # https://stackoverflow.com/questions/9823936/how-do-i-determine-what-type-of-exception-occurred
                        template = "UNHANDLED: An exception of type {0} occurred.\nArguments:\n{1!r}"
                        message = template.format(type(ex).__name__, ex.args)
                        print(message)
    
                # Capture any outputs needed for decision routing
                produces = route.get("produces", {})
                if produces:
                    session_artifacts = session.setdefault("workflow_artifacts",{})
                    responses = result["result"].get("responses", {})
                    for artifact_name, source_node in produces.items():
                        if source_node in responses:
                            session_artifacts[artifact_name] = responses[source_node]
                    session["workflow_artifacts"] = session_artifacts


                # ----------------------------------
                # CHECK INTERRUPT
                # ----------------------------------
                if registry.interrupt:
                    intr = registry.interrupt
                    reason = intr.get(
                        "reason",
                        "failure"
                    )
                    print(reason)
                    if reason == "ui":
                        return render_ui_interrupt(intr)
                    if reason == "competency":

                        return f"""
                        <h2>
                        Competency Refresh Required
                        </h2>

                        <p>
                        This task has been assigned
                        manually to maintain
                        operational readiness.
                        </p>

                        <p>
                        <b>Agent:</b>
                        {intr['node']}
                        </p>

                        <pre>
                        {intr['failed_input']}
                        </pre>

                        <form method="POST">

                          <input
                             type="hidden"
                             name="state_id"
                             value="{intr['state_id']}">

                          <textarea
                             name="prompt"
                             rows="8"
                             style="width:100%;">
                          </textarea>

                          <button type="submit">
                          Complete Task
                          </button>

                        </form>
                        """
                        
                    sid = intr["state_id"]
                    node = intr["node"]
                    failed_input = intr["failed_input"]

                    return f"""
                    <h2>Human Input Required</h2>

                    <p><b>Agent:</b> {node}</p>

                    <p><b>Input:</b></p>
                    <pre>{failed_input}</pre>

                    <form method="POST">
                        <input type="hidden" name="state_id" value="{sid}">
                        <textarea name="prompt" rows="8" style="width:100%;"></textarea><br><br>
                        <button type="submit">Submit</button>
                    </form>
                    """

                # String summary for display use
                token_use = json.dumps(result['tokens'], indent=4, default=safe_serialize)

                # --- decision support
                decision = DECISIONS.get(route["path"])
                show_prompt=True
                decision_html = ""
                # This works for --use-failing-client, but what about when you are connected...
                if (decision and "options" in decision) and (result.get('needs_prompt',True)==False):
                    decision_html += (f"<h2>{decision.get('question', 'Next Step')}</h2>")
                    for label, option in decision["options"].items():
                        next_path = option["path"]
                        decision_html += f"""
                        <form action="{next_path}"
                              method="GET"
                              style="display:inline;">
                             <input type="hidden" name="from_decision" value="true">
                            <button type="submit">
                                {label}
                            </button>
                        </form>
                        """
                    show_prompt = False 
                
                # ----------------------------------
                # NORMAL RESULT
                # ----------------------------------
                return render_template(
                        "prompt.html",
                        show_prompt=show_prompt, # not ideal - hiding the prompt when decision is needed    
                        preprompt=prompt,
                        response=f"""
                    <pre>{token_use}</pre>

                    <md-block>
                    {result['result']['trace']}
                    </md-block>

                    {decision_html}
                    """
                    )

            return flask_handler

        app.add_url_rule(
            route["path"],
            endpoint=endpoint_name,
            view_func=make_flask_handler(route, handler),
            methods=route.get("methods", ["GET", "POST"])
        )



@app.route("/graph/<string:name>", methods=["GET"])
def graph(name):
    global ROUTES
    
    for route in ROUTES:
        endpoint_name = route.get("name") or route["path"].strip("/").replace("-", " ").title()
        if name==endpoint_name:
            workflow = route.get("workflow")
            produces = route.get("produces", {})
            if workflow is None:
                agent_dir = route.get("agent_dir",None)
                if not os.path.exists(os.path.join(agent_dir,'config.json')):
                    return f"{name} not found in ROUTES. No graph page created.", 404
                with open(os.path.join(route["agent_dir"], 'config.json'), encoding="utf-8") as f:
                    workflow =  json.load(f)

            # workflow now contains a dictionary where the keys are the nodes and the values are lists of the parents of that node.
            # create a basic dot language graph
            lines = []
            lines.append('digraph G {')
            lines.append("""
            bgcolor="white";

            graph [
                fontname="Helvetica",
                fontsize=10
            ];

            node [
                shape=box,
                style="rounded,filled",
                fontname="Helvetica",
                fontsize=10,
                fillcolor="#F5F7F8",
                color="#D8DDE1",
                fontcolor="#0E1113"
            ];

            edge [
                color="#6B747B",
                arrowsize=0.7
            ];
            """)
            

            declared = set()

            for node in workflow:
                declared.add(node)
                lines.append(f'"{node}";')

            for child, parents in workflow.items():
                for parent in parents:
                    if parent not in declared:
                        declared.add(parent)
                        lines.append(f'"{parent}" [shape=ellipse, fillcolor="#DFF4FF"];')
                    lines.append(f'"{parent}" -> "{child}";')
                    

            lines.append('}')
            dotgraph =  "\n".join(lines)
            return render_template("graph.html",
                           original_graph=dotgraph)

    return f"{name} not found in ROUTES. No graph page created.", 404



# ----------------------------------
# Index
# ----------------------------------

@app.route("/", methods=["GET"])
def index():
    global ROUTES
    global DECISIONS

    html = ["<h1>Available Workflows</h1>"]

    decision_targets = set()

    for d in DECISIONS.values():
        for option in d.get("options", {}).values():
            decision_targets.add(option["path"])

    for route in ROUTES:
        path = route["path"]

        # don't show routes that are only
        # reachable from decisions
        if path in decision_targets:
            continue

        name = (
            route.get("name")
            or path.strip("/")
                  .replace("-", " ")
                  .title()
        )

        html.append(
            f'<h2><a href="{path}">{name}</a></h2>'
            f' <h3><a href="/graph/{name}">'
            f'Graph of {name}</a></h3>'
        )

    return "\n".join(html)

# ----------------------------------
# Run
# ----------------------------------
import argparse

def parse_args():
    parser = argparse.ArgumentParser(description="Run the Flask LLM app")

    parser.add_argument(
        "--deployment",
        type=str,
        default="gpt-4.1", # qwen3.6-colibri
        help="Model deployment name"
    )

    parser.add_argument(
        "--config",
        type=str,
        default="routes.yaml",
        help="Path to routes configuration file"
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable Flask debug mode"
    )

    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host for Flask app"
    )

    parser.add_argument(
        "--port",
        type=int,
        default=5000,
        help="Port for Flask app"
    )

    parser.add_argument(
        "--use-failing-client",
        action="store_true",
        help="Use FailingClient instead of AzureOpenAIClient"
    )

    parser.add_argument(
        "--use-resumable-registry",
        action="store_true",
        help="Wrap registry with ResumableRegistry"
    )

    parser.add_argument(
        "--use-resilient-registry",
        action="store_true",
        help="Wrap registry with ResilientRegistry"
    )

    parser.add_argument(
        "--user",
        type=str,
        default=None,
        help="user name (matched against registered users lists)"
    )

    args = parser.parse_args()

    # Validation
    if args.use_resilient_registry and not args.user:
        parser.error(
            "--use-resilient-registry requires --user <username>. "
            "The resilient registry can only be used for registered users."
        )

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    # Client selection
    use_failing = False
    if args.use_failing_client:
        use_failing = True
    if use_failing:
        client = FailingClient()
    else:
        creds = getLLM()
        if creds is None:
            client = FailingClient()
            use_failing=True            
        else:
            client = AzureOpenAIClient(getLLM())

    # Registry selection
    base_registry = AgentRegistry()
    if args.use_resilient_registry:
        registry = ResilientRegistry(base_registry, default_user=args.user)
    elif args.use_resumable_registry or use_failing:
        registry = ResumableRegistry(base_registry)
    else:
        registry = base_registry


    # Config + build
    set_routes(args.config)
    build_app(app, client, registry, args.deployment)

    # Run server
    app.run(
        host=args.host,
        port=args.port,
        debug=args.debug
    )
