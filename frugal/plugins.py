import os
from pathlib import Path
import importlib.util
import sys

# ----------------------------------
# Plugin Loader (from an agent_dir)
# ----------------------------------
def load_agent_plugins(agent_dir):
    """
    Dynamically import visitor/plugins from the agent directory.
    This allows agent authors to ship their own ResponseVisitor subclasses.
    """

    # Support either a single visitors.py OR a plugins folder
    candidates = []

    visitors_file = os.path.join(agent_dir, "visitors.py")
    if os.path.exists(visitors_file):
        candidates.append(visitors_file)

    plugins_dir = os.path.join(agent_dir, "plugins")
    if os.path.isdir(plugins_dir):
        for file in os.listdir(plugins_dir):
            if file.endswith(".py"):
                candidates.append(os.path.join(plugins_dir, file))

    for path in candidates:
        module_name = f"plugin_{hash(path)}"

        spec = importlib.util.spec_from_file_location(module_name, path)
        module = importlib.util.module_from_spec(spec)

        sys.modules[module_name] = module
        spec.loader.exec_module(module)
