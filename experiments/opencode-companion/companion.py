#!/usr/bin/env python3
"""Resumable whole-workshop controller, with explicit bounded platform actions."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parent
STATE = Path(os.environ.get("COMPANION_STATE", str(ROOT / ".progress.json")))
WORKSHOP = Path(os.environ.get("WORKSHOP_REPO", str(ROOT.parents[1])))
ANSWERS = ["B", "B", "C", "A", "B", "B", "C", "A", "A", "B"]
FEEDBACK = [
    "Use the assigned existing cluster and bastion; RHDP already manages their lifecycle and billing.",
    "The GPU executes inference; the CPU workers run the platform and development services.",
    "Operators reconcile desired configuration continuously, including after a pod restart.",
    "MaaS adds authenticated access and token quotas in front of the inference service.",
    "AGENTS.md provides the coding agent's rules, alongside the prepared application template.",
    "Dev Spaces injects tools and credentials into a persistent browser workspace.",
    "Tekton builds the image; Argo CD reconciles the application with its Git configuration.",
    "Check resource requests and limits, probes, restricted pod security, and HTTPS.",
    "DCGM measures GPU activity, while vLLM records prompt and generated tokens.",
    "OpenCode generates the application, Tekton builds its image, and Argo CD reconciles it from Git.",
]


def host_env():
    env = os.environ.copy()
    # OpenCode has private XDG directories. ROSA/OCM must retain the bastion's
    # own config locations and its already authenticated workshop account.
    for name in ["XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME", "XDG_STATE_HOME"]:
        original = env.get("WORKSHOP_HOST_" + name)
        if original:
            env[name] = original
        else:
            env.pop(name, None)
    return env


def oc(*args):
    result = subprocess.run(["oc", "--request-timeout=20s", *args], capture_output=True, text=True, timeout=30, env=host_env())
    if result.returncode:
        raise RuntimeError("OpenShift read failed; check your login and access.")
    return json.loads(result.stdout) if result.stdout.strip().startswith(("{", "[")) else result.stdout.strip()


def get(kind, name=None, namespace=None):
    args = ["get", kind]
    if name:
        args.append(name)
    if namespace:
        args.extend(["-n", namespace])
    return oc(*args, "-o", "json")


def condition(resource, name):
    return any(c["type"] == name and c["status"] == "True" for c in resource.get("status", {}).get("conditions", []))


def request(url, token, body=None):
    payload = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(url, data=payload, headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=45) as response:
        return json.load(response)


def verify_existing(index):
    if index == 0:
        nodes = get("nodes")["items"]
        gpu = [n for n in nodes if int(n["status"].get("allocatable", {}).get("nvidia.com/gpu", "0")) > 0]
        assert gpu and all(condition(n, "Ready") for n in gpu), "No Ready GPU with allocatable capacity."
        assert any(any(t["key"] == "nvidia.com/gpu" and t["effect"] == "NoSchedule" for t in n["spec"].get("taints", [])) for n in gpu), "GPU isolation taint missing."
        return {"gpu_nodes": len(gpu), "cpu_nodes": len(nodes) - len(gpu), "gpu_allocatable": True, "gpu_taint": "NoSchedule"}
    if index == 1:
        dsc = get("datasciencecluster", "default-dsc")
        names = ["KserveReady", "ModelsAsAServiceReady", "AIGatewayReady", "DashboardReady", "OGXReady"]
        assert all(condition(dsc, n) for n in names), "A platform component is not Ready."
        assert get("checluster", "devspaces", "openshift-operators")["status"]["chePhase"] == "Active", "Dev Spaces is not Active."
        return {"ready_components": names, "dev_spaces": "Active"}
    if index == 2:
        assert condition(get("llminferenceservice", "qwen3", "llm-serving"), "Ready"), "Model is not Ready."
        base = os.environ.get("OPENAI_BASE_URL", "")
        key = os.environ.get("OPENAI_API_KEY", "")
        assert base.startswith("https://") and key.startswith("sk-oai-"), "Prepare the companion's MaaS configuration on the bastion."
        host = urllib.parse.urlsplit(base).netloc
        models = request("https://" + host + "/v1/models", key)
        assert any(m.get("owned_by") == "llm-serving/qwen3" and m.get("ready") for m in models.get("data", [])), "Workshop model is missing from discovery."
        result = request(base.rstrip("/") + "/chat/completions", key, {"model": "qwen3", "messages": [{"role": "user", "content": "Reply with exactly COMPANION_OK"}], "max_tokens": 20, "chat_template_kwargs": {"enable_thinking": False}})
        assert "COMPANION_OK" in result["choices"][0]["message"]["content"], "Unexpected model response."
        return {"model": "Qwen3.8", "discovery": "Ready", "real_inference": "COMPANION_OK", "credentials": "not displayed"}
    if index == 3:
        ns = os.environ.get("WORKSHOP_WORKSPACE_NAMESPACE", "cluster-admin-devspaces")
        workspaces = get("devworkspace", namespace=ns)["items"]
        running = [w["metadata"]["name"] for w in workspaces if w.get("status", {}).get("phase") == "Running"]
        assert running, "No running Dev Space in the configured namespace."
        return {"running_workspaces": running, "namespace": ns}
    if index == 4:
        app = os.environ.get("APP_NAME", "fortune-cookie")
        resource = get("application", app, app + "-dev")
        assert resource["status"]["sync"]["status"] == "Synced" and resource["status"]["health"]["status"] == "Healthy", "Application is not Synced and Healthy."
        runs = get("pipelineruns", namespace=app + "-build")["items"]
        succeeded = sum(condition(r, "Succeeded") for r in runs)
        assert succeeded, "No successful image build."
        host = get("route", app, app + "-dev")["spec"]["host"]
        with urllib.request.urlopen("https://" + host + "/healthz", timeout=20) as response:
            assert json.load(response) == {"status": "ok"}, "Application health check failed."
        return {"successful_builds": succeeded, "sync": "Synced", "health": "Healthy", "application": "https://" + host}
    host = get("route", "thanos-querier", "openshift-monitoring")["spec"]["host"]
    token = oc("whoami", "-t")
    values = {}
    for query in ["DCGM_FI_DEV_GPU_UTIL", 'vllm:generation_tokens_total{namespace="llm-serving"}', 'vllm:prompt_tokens_total{namespace="llm-serving"}']:
        result = request("https://" + host + "/api/v1/query?" + urllib.parse.urlencode({"query": query}), token)
        rows = result.get("data", {}).get("result", [])
        assert rows, "A workshop metric has no series."
        values[query] = sum(float(row["value"][1]) for row in rows)
    subscription = get("maassubscription", "qwen3-workshop", "models-as-a-service")
    assert subscription["status"]["phase"] == "Active", "Subscription is not Active."
    return {"metrics": values, "subscription": "Active", "note": "GPU utilization can be zero when idle; token counters are cumulative."}


def verify(index):
    if index == 0:
        result = subprocess.run(["bash", str(WORKSHOP / "scripts/onboard.sh")], capture_output=True, text=True, timeout=90, env=host_env())
        assert result.returncode == 0, "Bastion onboarding check failed; run bash scripts/onboard.sh from the workshop repository."
        account = subprocess.run(["aws", "sts", "get-caller-identity", "--query", "Account", "--output", "text"], capture_output=True, text=True, timeout=30, env=host_env())
        assert account.returncode == 0, "The assigned AWS session is unavailable."
        return {"host": "RHDP bastion / Cloud Terminal", "user": oc("whoami"), "aws_account": account.stdout.strip(), "onboarding": "passed"}
    if index == 4:
        che = get("checluster", "devspaces", "openshift-operators")
        assert che["status"].get("chePhase") == "Active", "Dev Spaces is not Active."
        url = che["status"]["cheURL"].rstrip("/")
        return {"developer_launch_url": url + "/#https://github.com/fjcloud/go-app-template?ai-provider=opencodeai/opencode", "guide": "https://fjcloud.github.io/rosa-ai-app-platform/modules/200-platform/lab_5_agents_md.html", "companion_host": "Still the bastion; no Dev Space is required for the companion."}
    if index == 7:
        app = os.environ.get("APP_NAME", "fortune-cookie")
        deployment = get("deployment", app, app + "-dev")
        spec = deployment["spec"]["template"]["spec"]
        c = spec["containers"][0]
        assert c["resources"]["requests"] == {"cpu": "50m", "memory": "64Mi"}, "Resource requests differ from the workshop rules."
        assert c["resources"]["limits"] == {"cpu": "200m", "memory": "128Mi"}, "Resource limits differ from the workshop rules."
        assert all(c[p]["httpGet"]["path"] == "/healthz" for p in ["readinessProbe", "livenessProbe"]), "Health probes are missing."
        assert spec["securityContext"]["runAsNonRoot"] and not c["securityContext"]["allowPrivilegeEscalation"], "Restricted security settings are missing."
        tls = get("route", app, app + "-dev")["spec"]["tls"]
        assert tls["termination"] == "edge" and tls["insecureEdgeTerminationPolicy"] == "Redirect", "Route HTTPS settings differ."
        return {"resources": "workshop limits verified", "probes": "/healthz", "security": "restricted", "https": "edge + Redirect"}
    if index == 9:
        return {"application": verify_existing(4), "workshop": "Acts 0–3 explored from Cloud Terminal"}
    return verify_existing({1: 0, 2: 1, 3: 2, 5: 3, 6: 4, 8: 5}[index])


def guide(lesson):
    path = WORKSHOP / "content/modules/ROOT/pages" / lesson["source_file"]
    return {"path": str(path), "content": path.read_text()[:22000]}


def run_step(index):
    # Reconcile only the platform portions of the guide, and only on explicit
    # learner request. An already verified deployed step is left in place.
    try:
        return {"already_complete": True, "evidence": verify(index)}
    except Exception:
        pass
    if index not in [2, 3]:
        return {"manual_step": True, "instruction": "Read the current guide and show its commands or browser action. Do not improvise cloud creation or developer code from this controller."}
    commands = [["oc", "apply", "-k", "deploy/operators"]] if index == 2 else [
        ["oc", "apply", "-k", "deploy/tasks"],
        ["oc", "apply", "-k", "deploy/instances"],
        ["bash", "deploy/instances/configure-platform.sh"],
        ["oc", "apply", "-k", "deploy/inference"],
    ]
    for command in commands:
        result = subprocess.run(command, cwd=WORKSHOP, stdout=sys.stderr, stderr=sys.stderr, timeout=900, env=host_env())
        if result.returncode:
            raise RuntimeError("Workshop command failed; inspect the terminal output before retrying.")
    return {"requested": True, "instruction": "Run the live check; if resources are still starting, explain the wait and offer Retry."}


def save(state):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    temporary = STATE.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, indent=2) + "\n")
    temporary.replace(STATE)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["status", "lesson", "guide", "run", "check", "answer", "next"])
    parser.add_argument("choice", nargs="?", choices=["A", "B", "C"])
    args = parser.parse_args()
    course = json.loads((ROOT / "course.json").read_text())
    state = json.loads(STATE.read_text()) if STATE.exists() else {"step": 0, "checks": {}, "quizzes": {}, "completed": []}
    i = state["step"]
    key = str(i)
    output = {"step": i + 1, "total": len(course), "title": course[i]["title"], "check_passed": state["checks"].get(key, False), "quiz_passed": state["quizzes"].get(key, False), "completed": state["completed"], "finished": len(state["completed"]) == len(course)}
    if args.action == "lesson":
        output["lesson"] = course[i]
    elif args.action == "guide":
        output["guide"] = guide(course[i])
    elif args.action == "run":
        try:
            output["execution"] = run_step(i)
        except Exception as error:
            output["error"] = str(error) if isinstance(error, RuntimeError) else type(error).__name__
    elif args.action == "check":
        try:
            output["evidence"] = verify(i)
            state["checks"][key] = True
        except Exception as error:
            state["checks"][key] = False
            output["error"] = str(error) if isinstance(error, (AssertionError, RuntimeError)) else type(error).__name__
        output["check_passed"] = state["checks"][key]
        save(state)
    elif args.action == "answer":
        if args.choice is None:
            parser.error("answer requires A, B or C")
        correct = args.choice == ANSWERS[i]
        state["quizzes"][key] = correct
        save(state)
        output.update(correct=correct, quiz_passed=correct, feedback=FEEDBACK[i] if correct else "Try again. " + course[i]["hint"])
    elif args.action == "next":
        if not state["checks"].get(key) or not state["quizzes"].get(key):
            output["blocked"] = "Verify the live checkpoint and answer the quiz first."
        else:
            if i not in state["completed"]:
                state["completed"].append(i)
            if i + 1 == len(course):
                output["finished"] = True
                output["completed"] = state["completed"]
            else:
                state["step"] += 1
                output = {"step": state["step"] + 1, "total": len(course), "lesson": course[state["step"]]}
            save(state)
    print(json.dumps(output, ensure_ascii=False))


if __name__ == "__main__":
    main()
