from frugal.visitors import register_visitor, ResponseVisitor

# Example of a simple viaitor that writes the output of specific agents to file
@register_visitor("ExportVisitor")
class ExportVisitor(ResponseVisitor):

    def __init__(self, prompt, agent_dir=None, workflow=None, registry=None, client=None, deployment=None, **kwargs):
        super().__init__(prompt)
        self.outputs = []
        self.agent_dir = agent_dir
        self.workflow = workflow
        self.registry = registry
        self.client = client
        self.deployment = deployment
        self.prompt = prompt


    def process_response(self, agent_name=None, response=None, inputs=None, tokens={}):
        export_list = ["MiniZINCAgent"]
        if agent_name in export_list:
            response = response.replace("```lisp","")
            response = response.replace("```","")

            with open(agent_name + ".mzn", "w", encoding="utf-8") as f:
                f.write(response)

    def finalize(self):
        pass
