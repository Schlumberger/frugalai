from frugal.agents import BaseAgent

class CodeGenerationAgent(BaseAgent):
    def __init__(self, azure_openai_client, config):
        super().__init__(azure_openai_client, config)

    def prompt(self, user_prompt: str):
        # correct common LLM errors
        user_prompt = user_prompt.replace("```python","")
        user_prompt = user_prompt.replace("```","")

        with open('./output_code.py','w',encoding='utf-8') as f:
            f.write(user_prompt)
        return user_prompt # a simple pass through

