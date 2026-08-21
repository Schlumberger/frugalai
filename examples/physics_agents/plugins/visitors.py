from frugal.visitors import register_visitor, ResponseVisitor
from frugal.engine import AgenticWorkflowEngine

# NOTE: The visitor belongs to the workflow it augments, not to the workflows it executes
# YAML
# visitor: StyleVisitor
# visitor_args:
#  workflows:
#  - agent_dir: ../style_agents
#
@register_visitor("StyleVisitor")
class StyleVisitor(ResponseVisitor):

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
        self.outputs.append({
            "agent": agent_name,
            "response": response,
            "tokens" : tokens,
            "inputs": inputs
        })

    def finalize(self):
        """
        Run a secondary workflow after the main one finishes.
        """
        engine = AgenticWorkflowEngine(
            self.registry,
            self.client,
            self.deployment
        )
        
        engine.load_agents(self.agent_dir)

        workflow = engine.load_workflow(
            self.agent_dir,
            self.workflow
        )

        # REPORT STRUCTURE - ReportAgent is first... then the rest...
        report_structure = ["ReportAgent","IntentAgent","ClassifierAgent",
                            "PartitionerAgent","EquationAgent","DimensionlessAgent",
                            "AdmissibilityAgent",
                            "ConstitutiveClosureAgent","ChemistryAndMaterialsAgent","LimitsAgent",
                            "CausalSummaryAgent","CredibilityAgent"]
        # report_structure = ["ReportAgent","EquationAgent","DimensionlessAgent"]


        

        # Restyle and format using style_agents...
        results = {}
        markdown = {}
        for output in self.outputs:
            if output['agent'] in report_structure: # only apply to the report...
                result = engine.execute(
                    output['response'],
                    workflow,
                    response_visitor = None # limit the nesting to avoid any risk of infinite recursion...
                )
                results[output['agent']]=result['final_response']
                markdown[output['agent']]=output['response']



        # Two reports created together - Latex for people, Markdown for LLM (e.g. IProva)
        out_md = ""            
        out_latex = ""
        for section in report_structure:
            out_md += f"\n## {section}\n"
            out_md += markdown[section]
            out_md += "\n"
            out_latex += "\n\\part{"+section+"}\n"
            out_latex += results[section]
            out_latex += "\n\n\\pagebreak\n"
            if section=="ReportAgent":
                out_md += f"\n## Supplementary Information\n\n### Prompt\n{self.prompt}\n"
                out_latex += "\n\\part{Supplementary Information}\n\n"
                out_latex += "\n\\section*{Prompt}\n"
                out_latex += f"\n{self.prompt}\n\\pagebreak\n"

        with open('content.md','w',encoding='utf-8') as f:
            f.write(out_md)
            
        with open('content.tex','w',encoding='utf-8') as f:
            f.write(out_latex)

        # Replace final response
        self.response = result["final_response"]

