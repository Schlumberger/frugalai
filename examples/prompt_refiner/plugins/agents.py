import os
import json
from frugal.agents import BaseAgent

class ExtractAgent(BaseAgent):
    def __init__(self, azure_openai_client, config):
        super().__init__(azure_openai_client, config)

    def prompt(self, user_prompt: str):
        data = json.loads(user_prompt)

        # guarantee that the directory exists
        os.makedirs('./automation/agents', exist_ok=True)

        dag = {}
        for node in data:
            dag[node]=data[node]["parents"]
            agent_json = f"""
{{
  "name": "{node}",
  "description": "{data[node]['purpose']}",
  "system_prompt_file" : "{node[:-5]}_prompt.txt",   
  "temperature": 0.7,
  "max_tokens": 32000
}}
"""
            with open(f"./automation/agents/{node[:-5]}_agent.json","w",encoding="utf-8") as f:
                f.write(agent_json)

            with open(f"./automation/agents/{node[:-5]}_prompt.txt","w",encoding="utf-8") as f:
                f.write(f"# System Prompt for {node}")


        with open(f"./automation/config.json","w",encoding="utf-8") as f:
            f.write(json.dumps(dag))

        return json.dumps(dag)
    
