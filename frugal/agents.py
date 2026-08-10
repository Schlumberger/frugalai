# frugal\agents.py
# see LICENSE

from abc import ABC, abstractmethod

import json
import importlib.util
from pathlib import Path
import tiktoken

# helper for serialization
def to_serializable(obj):
    # Base cases
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj

    if isinstance(obj, dict):
        return {k: to_serializable(v) for k, v in obj.items()}

    if isinstance(obj, (list, tuple)):
        return [to_serializable(v) for v in obj]

    # SDK objects (like CompletionUsage)
    if hasattr(obj, "__dict__"):
        return {
            k: to_serializable(v)
            for k, v in obj.__dict__.items()
            if not k.startswith("_")  # skip private attrs
        }

    # Fallback
    return str(obj)


# Agent exceptions
class TooManyTokens(Exception):
    def __init__(self, message, filename, lineno):
        super().__init__(message)
        self.filename = filename
        self.lineno = lineno
        self.message = message

    def __str__(self):
        return f"{self.message} in {self.filename} at line {self.lineno}"

class LLMFailed(Exception):
    def __init__(self, message, filename, lineno):
        super().__init__(message)
        self.filename = filename
        self.lineno = lineno
        self.message = message

    def __str__(self):
        return f"{self.message} in {self.filename} at line {self.lineno}"

class Client(ABC):
    @abstractmethod
    def chat(self,model=None,temperature=None,max_tokens=None,messages=None):
        # return the response
        pass

class BaseAgent:
    def __init__(self, client, config, deployment_name="gpt-4.1"):
        self.client = client
        self.name = config["name"]
        self.description = config["description"]
        self.system_prompt = config["system_prompt"]
        self.user_prompt = config["user_prompt"]
        self.deployment_name = config["deployment_name"]
        self.temperature = config.get("temperature", 0.3)
        self.max_tokens = config.get("max_tokens", 5000)
        self.max_prompt_tokens = config.get("max_prompt_tokens",65000)
        self.memory = []
        self.token_counter = []

    # NOTE - duplicate of function in patent_funcs - 
    def num_tokens_from_string(self, stringval: str, encoding_name: str, claude=False) -> int:
        # Claude has a long context window and strips some tokens
        # see https://markaicode.com/integrate/tiktoken-with-anthropic/
        if claude==True:
            # NOTE: The default cl100k_base is recommended in the reference, this is left as a user responsibility
            #       as it may change in the future so we don't want it hard-coded here.
            stringval = stringval.lstrip("\ufeff").strip() # compress multiple spaces
            stringval = stringval.replace("\u200b","")     # remove zero length spaces
            # NOTE: Anthropic's own token counter requires Anthropic API-key and function call so is not suitable
            #       for stand-alone workflow design tools. No dependency on API calls in this library!
        encoding = tiktoken.get_encoding(encoding_name)
        num_tokens = len(encoding.encode(stringval))
        return num_tokens


    def prompt(self, user_prompt: str, checkpoint_path="agent_state.json"):
        up = self.user_prompt.replace("<response>", user_prompt)

        # Calling externally (the LLM) so handle exceptions gracefully
        # The failure mode is to return the full system_prompt + user_prompt
        # ...this supports the user to investigate.
        if self.num_tokens_from_string(up, "cl100k_base") > self.max_prompt_tokens:
            # Save before failing
            self.save(checkpoint_path)
            raise TooManyTokens("Too many tokens for user prompt", "agents.py", 84)

        messages = [
            {"role": "system", "content": self.system_prompt},
            *self.memory,
            {"role": "user", "content": up}
        ]

        try:
            response = self.client.chat(
                model=self.deployment_name,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                messages=messages
            )
        except Exception as e:
            # checkpoint on failure
            self.save(checkpoint_path)
            
            raise LLMFailed(f"""# {self.name}
## Failed for...
### System Prompt

{self.system_prompt}

### User Prompt

{up}

### Debug Context

{self.to_dict()}
""","agents.py", 103)

        reply = response.choices[0].message.content
        
        self.token_counter.append(response.usage)

        # Only commit state AFTER success
        self.memory.append({"role": "user", "content": up})
        self.memory.append({"role": "assistant", "content": reply})

        return reply
    
    def reset(self):
        self.memory.clear()

    def get_token_usage(self):
        return self.token_counter

    def to_dict(self):
        return {
            "name": self.name,
            "description": self.description,
            "system_prompt": self.system_prompt,
            "user_prompt": self.user_prompt,
            "deployment_name": self.deployment_name,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "max_prompt_tokens": self.max_prompt_tokens,
            "memory": to_serializable(self.memory),
            "token_counter": to_serializable(self.token_counter)
        }

    @classmethod
    def from_dict(cls, client, state: dict):
        agent = cls(client, state)
        agent.memory = state.get("memory", [])
        agent.token_counter = state.get("token_counter", [])
        return agent

    # persist to disc...
    def save(self, path: str):
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)


    @classmethod
    def load(cls, client, path: str):
        with open(path, "r") as f:
            state = json.load(f)
        return cls.from_dict(client, state)


class AgentFactory:
    @staticmethod
    def load_config(path: Path):
        with open(path, "r", encoding="utf-8") as f:
            cfg = json.load(f)

        # Hold onto the diretory (in case we are asked to load an external agent
        cfg["_config_dir"] = str(path.parent)

        # Load system prompt if referenced as a file
        if "system_prompt_file" in cfg:
            spath = path.parent / cfg["system_prompt_file"]
            with open(spath, "r", encoding="utf-8") as f:
                cfg["system_prompt"] = f.read()

        # auxiliary file - e.g. DESIGN.md or LANGUAGE.md 
        if "aux_file" in cfg:
            spath = path.parent / cfg["aux_file"]
            with open(spath, "r", encoding="utf-8") as f:
                data = f.read()
                cfg["system_prompt"] = cfg["system_prompt"].replace("<response>",data)

        cfg["user_prompt"] = "<response>"
        if "user_prompt_file" in cfg:
            spath = path.parent / cfg["user_prompt_file"]
            with open(spath, "r", encoding="utf-8") as f:
                data = f.read()
                cfg["user_prompt"] = cfg["user_prompt"].replace("<response>",data)

        return cfg

    
    @staticmethod
    def create_agent(client, config):
        agent_type = config.get("type", "llm")

        # Default LLM agent
        if agent_type == "llm" or agent_type is None:
            return BaseAgent(client, config)

        return AgentFactory._load_python_agent(agent_type, client, config)

    @staticmethod
    def _load_python_agent(type_path, client, config):
        base_dir = Path(config["_config_dir"]).parent
        path = (base_dir / type_path).resolve()
        
        #path = Path(type_path)

        if not path.exists():
            raise FileNotFoundError(f"Agent module not found: {type_path}")

        module_name = path.stem

        spec = importlib.util.spec_from_file_location(module_name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        class_name = config["name"]

        if not hasattr(module, class_name):
            raise AttributeError(
                f"{type_path} does not define class '{class_name}'"
            )

        AgentClass = getattr(module, class_name)

        return AgentClass(client, config)
    
