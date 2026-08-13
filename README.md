# frugalai

A minimal python module for AI-enabled workflow automation, which encourages cost discipline efficient model use through repeatable routing and lightweight abstractions for building reliable, scalable calculation graphs.

Whether automating the boring repetitive tasks, or dreaming of 10x productivity gains, it is hard to ignore the impact of the LLM-based agentic workflow.

Beneath the technology stack there are some relatively simple concepts that we believe are worth learning. Armed with that understanding, whether you a creating
workflows for yourself as a hobby, or managing a team building the AI-first business that will change the world, you can start to demand some requirements are met:
- **Frugal** – minimize unnecessary token use and have visibility over projected costs
- **Secure** – no direct path from generated text to commandline execution
- **Resumable** – be able to restart from any point in the agentic computation graph & recover from lost connection to the LLM
- **Resilient** – retain "stick-and-rudder" skills of your subject matter experts (SMEs)
- **Independent** – right-sizing the choice of LLM for every task
- **Hybrid** - non-LLM-based agents interacting directly with LLM-based agents.

The **frugal** module is designed so that you can build and deploy without the stack. The code is designed to be small and illustrative. Each file is small enough that you could paste it into your favourite LLM assistant and ask for it be explained. 

The **thrifty** example application offers no-code development of workflows, designed around multiple system prompts. It is a human-in-the-loop version of the automated "learning" of full enterprise-grade agent. YOu can use it to learn how actor-critic approaches operate; or to build and deploy complete AI-enabled workflows. 

The **examples** show what we have built, and we welcome contributions! We also welcome contributors to the core **frugal** library, noting that the priority is to keep everything small enough to read and learn from.



