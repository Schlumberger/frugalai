# frugal/visitors.py
# see LICENSE

VISITOR_REGISTRY = {}

def register_visitor(name):
    def wrapper(cls):
        VISITOR_REGISTRY[name] = cls
        return cls
    return wrapper


# ResponseVisitor
@register_visitor("DefaultVisitor")
class ResponseVisitor:
    def __init__(self, initial_prompt, **kwargs):
        self.response = initial_prompt
        self.tokens = {}

    # extract the prompt
    def get_prompt(self):
        return self.response

    # process stuff - the engine calls this
    def process_response(self, agent_name="UnknownAgent", response=None, inputs=None, tokens={}):
        self.response = response
        self.tokens[agent_name]= tokens

    # recover on end-of-life (happens at the end of the DAG processing)
    def finalize(self):
        pass

    # get local result from any intermediate step on the fly - the app calls this
    def get_result(self): 
        return {}

    # get token counts
    def get_tokens(self):
        return self.tokens
