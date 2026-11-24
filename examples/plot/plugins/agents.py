import json

from frugal.agents import BaseAgent
from frugal.resumable_registry import HumanInputRequired


class IngestAgent(BaseAgent):
    def prompt(self, user_prompt : str):
        return user_prompt

class DramaticSituationSelectionAgent(BaseAgent):

    def prompt(self, user_prompt: str):

        data = json.loads(user_prompt)

        raise HumanInputRequired({
            "type": "single_select_table",
            "title": "Choose Next Story Direction",
            "paragraph": data["paragraph"],
            "columns": [
                "Dramatic Situation",
                "Description",
                "score"
            ],
            "rows": data["decision_branch_table"]
        })
