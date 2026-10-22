"""Load the existing lab's MaaS configuration in memory and start OpenCode 2."""
import base64
import json
import os
from pathlib import Path
import subprocess
import sys

env = os.environ.copy()
# Keep explanations visible and hide raw controller output in the narrow panel.
env.setdefault("OPENCODE_CLI_CONFIG_CONTENT", json.dumps({"mini": {"tools": "show", "shell_output": "hide", "thinking": "hide", "turn_summary": "hide", "splash": "hide"}}))
if not env.get("OPENAI_API_KEY") or not env.get("OPENAI_BASE_URL"):
    result = subprocess.run(["oc", "get", "secret", "ai-provider-openai-api-key", "-n", "openshift-operators", "-o", "json"], capture_output=True, text=True, timeout=30)
    if result.returncode:
        raise SystemExit("This experiment needs the existing workshop's MaaS service. Log in to its cluster and prepare the model/API key first; no new key was created.")
    data = json.loads(result.stdout)["data"]
    for key in ["OPENAI_API_KEY", "OPENAI_BASE_URL"]:
        env[key] = base64.b64decode(data[key]).decode()
if not env["OPENAI_API_KEY"].startswith("sk-oai-") or not env["OPENAI_BASE_URL"].startswith("https://"):
    raise SystemExit("The existing MaaS configuration is invalid; check the workshop Secret.")
binary = Path.home() / ".local/share/rosa-companion/opencode2"
args = sys.argv[1:]
if not args:
    args = ["mini", "--prompt", "Guide-moi en français dans le workshop ROSA complet depuis Cloud Terminal. Commence à l'acte 0 si la progression est vide, sinon reprends l'étape sauvegardée. Charge rosa-companion. Explique une étape à la fois, propose ses commandes, vérifie le lab et pose des questions et un petit quiz. Attends mon choix pour avancer."]
elif args[0] in ["--continue", "-c", "--prompt", "--session", "-s"]:
    args.insert(0, "mini")
if args[0] in ["mini", "run"]:
    args.insert(1, "--standalone")
elif args[0] != "serve":
    args.insert(0, "--standalone")
os.execve(str(binary), [str(binary), *args], env)
