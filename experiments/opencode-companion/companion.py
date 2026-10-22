#!/usr/bin/env python3
"""Small, resumable course controller. Cluster operations are read-only."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parent
STATE = Path(os.environ.get("COMPANION_STATE", str(ROOT / ".progress.json")))
ANSWERS = ["B", "C", "A", "B", "C", "A"]
FEEDBACK = [
    "The GPU executes inference; the CPU workers run the platform and development services.",
    "Operators reconcile desired configuration continuously, including after a pod restart.",
    "MaaS adds authenticated access and token quotas in front of the inference service.",
    "Dev Spaces injects tools and credentials into a persistent browser workspace.",
    "Tekton builds the image; Argo CD reconciles the application with its Git configuration.",
    "DCGM measures GPU activity, while vLLM records prompt and generated tokens.",
]


def oc(*args):
    result = subprocess.run(["oc", "--request-timeout=20s", *args], capture_output=True, text=True, timeout=30)
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


def verify(index):
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
        assert base.startswith("https://") and key.startswith("sk-oai-"), "Use the Dev Space with its injected MaaS configuration."
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


def save(state):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    temporary = STATE.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, indent=2) + "\n")
    temporary.replace(STATE)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["status", "lesson", "check", "answer", "next"])
    parser.add_argument("choice", nargs="?", choices=["A", "B", "C"])
    args = parser.parse_args()
    course = json.loads((ROOT / "course.json").read_text())
    state = json.loads(STATE.read_text()) if STATE.exists() else {"step": 0, "checks": {}, "quizzes": {}, "completed": []}
    i = state["step"]
    key = str(i)
    output = {"step": i + 1, "total": len(course), "title": course[i]["title"], "check_passed": state["checks"].get(key, False), "quiz_passed": state["quizzes"].get(key, False), "completed": state["completed"], "finished": len(state["completed"]) == len(course)}
    if args.action == "lesson":
        output["lesson"] = course[i]
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
