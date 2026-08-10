# frugal/registry.py
# see LICENSE.

from pathlib import Path
from frugal.agents import AgentFactory

class AgentRegistry:
    def __init__(self):
        self.agents = {}

    def load_from_folder(self, folder: str, azure_openai_client, deployment="gpt-4.1"):
        folder_path = Path(folder)

        for file in folder_path.glob("*.json"):
            if file.name == 'config.json':
                continue # skip special case...
            cfg = AgentFactory.load_config(file)
            cfg['deployment_name']=deployment
            agent = AgentFactory.create_agent(azure_openai_client, cfg)
            self.agents[cfg["name"]] = agent

    def load_from_package(self, package, subdir, client, deployment):
        from importlib.resources import as_file, files
        resource = files(package).joinpath(subdir)
        with as_file(resource) as path:
            self.load_from_folder(path, client, deployment)

    def get(self, name):
        return self.agents.get(name)

    def list_agents(self):
        return list(self.agents.keys())
