# frugal/engine.py
# see LICENSE.

import os
import json
from pathlib import Path
import networkx as nx

class AgenticWorkflowEngine:
    def __init__(self, registry, client, deployment):
        self.registry = registry
        self.client = client
        self.deployment = deployment

    def load_agents(self, agent_dir):
        load_dir = os.path.join(agent_dir,'agents')
        print(load_dir)
        self.registry.load_from_folder(load_dir, self.client, self.deployment)

    def load_workflow(self, agent_dir, workflow=None):
        if workflow is not None:
            return workflow

        with open(os.path.join(agent_dir, 'config.json'), encoding="utf-8") as f:
            return json.load(f)


    def execute(self, prompt, workflow, response_visitor=None):
        token_tracker = []
        response_list = {}
        trace_output = [f"# Prompt\n{prompt}\n"]

        # Build graph
        G = nx.DiGraph()

        # handle the decision structure
        external_inputs = (self.registry.state.get("responses", {}))

        for node, deps in workflow.items():
            G.add_node(node)
            for dep in deps:
                if dep in workflow:
                    G.add_edge(dep, node)
                elif dep in external_inputs:
                    # artefact supplied by previous route
                    pass
                else:
                    raise ValueError(f"Unknown dependency '{dep}' for agent '{node}'")

        # Validate DAG
        if not nx.is_directed_acyclic_graph(G):
            cycles = list(nx.simple_cycles(G))
            raise ValueError(f"Cycle detected: {cycles}")

        # Get execution order
        execution_order = list(nx.topological_sort(G))

        # Execute in order
        for node in execution_order:
            agent = self.registry.get(node)
            if agent is None:
                raise ValueError(f"Agent '{node}' not found")

            deps = workflow[node]

            if deps:
                # updated to handle the external inputs which come in via the decisions
                parts = []
                for dep in deps:
                    if dep in response_list:
                        parts.append(response_list[dep])
                    elif dep in external_inputs:
                        parts.append(external_inputs[dep])
                    else:
                        raise ValueError(f"Unable to resolve dependency '{dep}'")
                input_text = "\n".join(parts)
            else:
                input_text = prompt

            try:
                response = agent.prompt(input_text)      
            except:
                # Allow for richer exception landscape (for example
                # the agent can throw the Frugal WorkflowInterrupt
                # or HumanInputRequired exceptions.
                # Here we delegate control over handling to the
                # app that is using Frugal
                raise

            token_use = agent.get_token_usage()
            token_tracker.extend(token_use)

            if response_visitor:
                response_visitor.process_response(agent_name=node, response=response, tokens=token_use)
            

            response_list[node] = response
            trace_output.append(f"# {node}\n{response}\n")

        if response_visitor:
            response_visitor.finalize()


        return {
            "prompt" : prompt,
            "final_response": response,
            "responses": response_list,
            "tokens": token_tracker,
            "trace": "\n".join(trace_output)
        }

