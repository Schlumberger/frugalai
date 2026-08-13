# frugal/resumable_registry.py
# see LICENSE

import json
import hashlib
from datetime import datetime
from pathlib import Path

class ResumableRegistry:
    def __init__(self, base_registry):
        self.base = base_registry
        self.state = None
        self.state_id = None
        self.interrupt = None
        
    def load_from_folder(self, *args, **kwargs):
        return self.base.load_from_folder(*args, **kwargs)

    def get(self, name):
        agent = self.base.get(name)
        return ResumableAgentWrapper(agent, name, self)

    def before_agent_execution(self, agent_name, input_text):
        print("before agent exection")
        # overridable behaviour for subclasses
        return None    


    # ----------------------------------
    # State persistence
    # ----------------------------------

    def _compute_id(self, state):
        s = json.dumps(state, sort_keys=True)
        return hashlib.sha256(s.encode()).hexdigest()[:12]

    def save_state(self, state):
        sid = self._compute_id(state)
        Path("states").mkdir(exist_ok=True)

        with open(f"states/{sid}.json", "w") as f:
            json.dump(state, f, indent=2)

        self.state = state
        self.state_id = sid
        return sid

    def load_state(self, sid):
        with open(f"states/{sid}.json") as f:
            self.state = json.load(f)
        self.state_id = sid
        return self.state

class ResumableAgentWrapper:
    def __init__(self, agent, name, registry):
        self.agent = agent
        self.name = name
        self.registry = registry

    def get_token_usage(self):
        return self.agent.get_token_usage()

    def prompt(self, input_text):
        print(f"[WRAPPER] Executing agent: {self.name}")
        system_prompt = self.agent.system_prompt # store it

        try:
            # if True:
            state = self.registry.state

            # SAFELY access state
            responses = {}
            if state and isinstance(state, dict):
                responses = state.get("responses", {})

            # ----------------------------------
            # interrupt the active state
            # ----------------------------------
            if self.registry.interrupt:
                return responses.get(self.name, "")

            # ----------------------------------
            # resume: return already completed nodes
            # ----------------------------------
            if state and self.name in responses:
                return responses[self.name]

            # ----------------------------------
            # resume: insert a human response
            # ----------------------------------
            if state and self.name == state.get("current_node"):
                try:
                    if state.get("human_response") is not None:
                        response = state["human_response"]
                        state.setdefault("responses", {})
                        state["responses"][self.name] = response
                        return response
                    return ""
                except Exception:
                    return ""

            # ----------------------------------
            # NORMAL EXECUTION
            # ----------------------------------
            try:
                action = self.registry.before_agent_execution(self.name, input_text)
                if action == "INTERRUPT":
                    return ""
                
                response = self.agent.prompt(input_text)
                print(response)

                return response

            except Exception as e:
                if not self.registry.interrupt:

                    workflow_state = {
                        "current_node": self.name,
                        "responses": responses,
                        "human_response": None,
                        "failed_input": input_text,
                        "error": str(e)
                    }

                    sid = self.registry.save_state(workflow_state)

                    self.registry.interrupt = {
                        "state_id": sid,
                        "node": self.name,
                        "failed_input": f"{system_prompt}\n\n{input_text}",
                        "error": str(e)
                    }

                return ""

        # ABSOLUTE SAFETY NET
        except Exception as fatal:
            print(f"[WRAPPER] FAILURE captured in agent: {self.name}")
            print(f"[WRAPPER] Error: {str(fatal)}")
            if not self.registry.interrupt:

                workflow_state = {
                    "current_node": self.name,
                    "responses": {},
                    "human_response": None,
                    "failed_input": input_text,
                    "error": f"FATAL: {str(fatal)}"
                }

                sid = self.registry.save_state(workflow_state)

                self.registry.interrupt = {
                    "state_id": sid,
                    "node": self.name,
                    "failed_input": f"{system_prompt}\n\n{input_text}",
                    "error": str(fatal)
                }

            return ""

