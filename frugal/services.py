# frugal/services.py
# see LICENSE

class PromptService:
    DEFAULT_PROMPT = "State your problem concisely, and grow the prompt by answering the questions"

    @staticmethod
    def resolve_prompt(visitor):
        prompt = visitor.get_prompt()
        if not prompt:
            return None, PromptService.DEFAULT_PROMPT
        return prompt, None
        for named_agent, dependencies in workflow.items():
            agent = self.registry.get(named_agent)

            # Resolve dependencies
            if dependencies:
                response = "\n".join(response_list[d] for d in dependencies)

            response = agent.prompt(response)
            token_tracker.extend(agent.get_token_usage())

            if response_visitor:
                response_visitor.process_response(response)

            response_list[named_agent] = response
            trace_output.append(f"# {named_agent}\n{response}\n")

        return {
            "final_response": response,
            "responses": response_list,
            "tokens": token_tracker,
            "trace": "\n".join(trace_output)
        }


class WorkflowRepository:
    @staticmethod
    def save_trace(trace, path="agentic_workflow_result.md"):
        with open(path, "w", encoding="utf-8") as f:
            f.write(trace)

