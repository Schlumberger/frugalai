# frugal/routing.py
# see LICENSE

import yaml

def load_routes_from_yaml(path):
    with open(path, "r") as f:
        config = yaml.safe_load(f)

    return config["routes"]


from frugal.plugins import load_agent_plugins
from frugal.engine import AgenticWorkflowEngine
from frugal.services import PromptService

def create_route(spec_entry, registry, client, deployment, visitor_registry):

    def handler(prompt):
        # any extra code, for example for custom visitors
        load_agent_plugins(spec_entry["agent_dir"])

        # Load + build engine
        engine = AgenticWorkflowEngine(registry, client, deployment)
        engine.load_agents(spec_entry["agent_dir"])

        workflow = engine.load_workflow(
            spec_entry["agent_dir"],
            spec_entry.get("workflow")
        )

        # Resolve visitor
        visitor_name = spec_entry.get("visitor", "DefaultVisitor")
        visitor_cls = visitor_registry.get(visitor_name)

        if visitor_cls is None:
            raise ValueError(f"Unknown visitor: {visitor_name}")

        visitor_args = spec_entry.get("visitor_args", {})
        # Visitors could be running agentic-workflows themselves
        response_visitor = visitor_cls(
            prompt,
            registry=registry,
            client=client,
            deployment=deployment,
            **visitor_args
        )


        # Handle empty prompt (moved out of engine)
        if not prompt:
            return {
                "needs_prompt": True,
                "result" : { "trace" : ""},
                "tokens" : {},
                "prompt": PromptService.DEFAULT_PROMPT
            }

        # Execute workflow
        result = engine.execute(prompt, workflow, response_visitor)

        token_count = {}
        if hasattr(response_visitor, "get_tokens"):
            token_count = response_visitor.get_tokens()
        
        if result.get("status") == "awaiting_human":
            return {
                "needs_prompt": True,
                "result": result,
                "tokens" : token_count,
                "prompt": ""
            }

        # possibly the visitor has a result to share...
        visitor_result = None
        if hasattr(response_visitor, "get_result"):
            visitor_result = response_visitor.get_result()

        return {
            "needs_prompt": False,
            "result": result,
            "prompt": prompt,
            "tokens" : token_count,
            "visitor_result": visitor_result
        }


    return handler

