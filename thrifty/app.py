import json
import sys
import os
from flask import Flask, request, render_template, session

from frugal.agents import Client
from frugal.registry import AgentRegistry
from frugal.routing import create_route, load_routes_from_yaml
from frugal.visitors import VISITOR_REGISTRY
from frugal.resumable_registry import ResumableRegistry
from frugal.resilient_registry import ResilientRegistry

##class HITLResponse:
##    def __init__(self, state_id, node):
##        self.state_id = state_id
##        self.node = node
##
##    def __str__(self):
##        return ""  # ensure engine doesn't break

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
    try:
        from openai import AzureOpenAI
    except:
        return None
    
    if not os.path.exists("./credfile.json"):
        return None
    
    with open("credfile.json") as f:
        credentials = json.load(f)

    cfg = credentials["default"]

    return AzureOpenAI(
        api_version=cfg['api_version'],
        azure_endpoint=cfg['endpoint'],
        api_key=cfg['credential']
    )



# ----------------------------------
# Client with human fallback
# ----------------------------------
class AzureOpenAIClient(Client):
    def __init__(self, client):
        self.client = client

    def chat(self, model=None, temperature=None, max_tokens=None, messages=None):
        response =  self.client.chat.completions.create(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            messages=messages
            )
        print(response)
        return response


class FailingClient(Client):
    def chat(self, *args, **kwargs):
        raise RuntimeError("Simulated LLM failure")



ROUTES = None

def set_routes(config_file):
    global ROUTES
    ROUTES = load_routes_from_yaml(config_file)


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

                if request.method == "POST":
                    prompt = request.form.get("prompt", "")
                    state_id = request.form.get("state_id")

                # RESUME path
                if state_id:
                    state = registry.load_state(state_id)
                    state["human_response"] = prompt
                    registry.state = state
                    registry.interrupt = None

                else:
                    registry.state = {"responses": {}}
                    registry.interrupt = None

                # RUN ENGINE
                result = handler(prompt)


                # ----------------------------------
                # CHECK INTERRUPT
                # ----------------------------------
                if registry.interrupt:

                    intr = registry.interrupt
                    reason = intr.get(
                        "reason",
                        "failure"
                    )
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
                
                # ----------------------------------
                # NORMAL RESULT
                # ----------------------------------
                return render_template(
                    "prompt.html",
                    preprompt=prompt,
                    response=f"""
    <pre>{token_use}</pre>
    <md-block>{result['result']['trace']}</md-block>"""
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
            

            for node in workflow:
               lines.append(f' {node};')


            for child, parents in workflow.items():
                for parent in parents:
                    lines.append(f'    {parent} -> {child};')

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

    html = ["<h1>Available Workflows</h1>"]

    for route in ROUTES:
        path = route["path"]
        name = route.get("name") or path.strip("/").replace("-", " ").title()

        html.append(f'<h2><a href="{path}">{name}</a></h2> <h3><a href="/graph/{name}">Graph of {name}</a></h3>')

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
        default="gpt-4.1",
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
