#!/usr/bin/env bash
# =============================================================================
# Platform Engineer E2E Validation Script
# =============================================================================
# Validates the full Platform Engineer workshop flow:
#   Phase 1 — GPU Machine Pool       (lab_1_gpu_machinepool)
#   Phase 2 — Cluster Operators      (lab_2_operators)
#   Phase 3 — Platform Instances     (lab_4_llm_service Step 1)
#   Phase 4 — LLM InferenceService   (lab_4_llm_service Step 2)
#   Phase 5 — Developer Template     (lab_5_agents_md)
#
# Prerequisites:
#   - oc is logged in with cluster-admin
# =============================================================================
set -euo pipefail

# ── Configuration ─────────────────────────────────────────────────────────────
GIT_SERVER="${GIT_SERVER:-https://gitpop.apps.sno.msl.cloud}"
TEMPLATE_URL="${TEMPLATE_URL:-https://github.com/fjcloud/go-app-template}"
GPU_INSTANCE_TYPE="${GPU_INSTANCE_TYPE:-g6e.xlarge}"
LLM_NS="${LLM_NS:-llm-inference}"
LLM_IS="${LLM_IS:-qwen36}"
LLM_URL_INTERNAL="http://${LLM_IS}-predictor.${LLM_NS}.svc.cluster.local:8080/v1"

# ── Colours ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

step()    { echo -e "\n${BOLD}${BLUE}══ $* ${NC}"; }
ok()      { echo -e "  ${GREEN}✅  $*${NC}"; }
warn()    { echo -e "  ${YELLOW}⚠️   $*${NC}"; }
fail()    { echo -e "  ${RED}❌  $*${NC}"; exit 1; }
info()    { echo -e "  ${CYAN}→  $*${NC}"; }

FAILURES=0

check() {
  local label=$1; shift
  if eval "$@" &>/dev/null; then
    ok "$label"
  else
    warn "FAIL: $label"
    FAILURES=$((FAILURES + 1))
  fi
}

csv_succeeded() {
  # Check specific namespaces — avoids permission issues on ROSA HCP with -A
  local pattern=$1
  for ns in redhat-ods-operator nvidia-gpu-operator openshift-nfd \
             openshift-operators openshift-gitops-operator openshift-pipelines \
             openshift-gitops; do
    if oc get csv -n "$ns" --no-headers 2>/dev/null \
        | grep -i "$pattern" | grep -q "Succeeded"; then
      return 0
    fi
  done
  return 1
}

# ── Preflight ─────────────────────────────────────────────────────────────────
step "Preflight checks"

command -v oc   &>/dev/null || fail "oc not found"
command -v curl &>/dev/null || fail "curl not found"
command -v git  &>/dev/null || fail "git not found"

info "Cluster: $(oc whoami --show-server)"
info "User:    $(oc whoami)"
info "Git server: $GIT_SERVER"
info "Template: $TEMPLATE_URL"

oc cluster-info &>/dev/null || fail "Not connected to a cluster"
ok "Cluster reachable"

# ─────────────────────────────────────────────────────────────────────────────
# PHASE 1 — GPU Machine Pool (lab_1_gpu_machinepool)
# ─────────────────────────────────────────────────────────────────────────────
step "Phase 1: GPU Machine Pool"

GPU_NODES=$(oc get nodes \
  -l "node.kubernetes.io/instance-type=${GPU_INSTANCE_TYPE}" \
  -o jsonpath='{.items[*].metadata.name}' 2>/dev/null || true)

if [[ -n "$GPU_NODES" ]]; then
  ok "GPU node(s) found with instance type ${GPU_INSTANCE_TYPE}: $(echo "$GPU_NODES" | wc -w) node(s)"
  info "Nodes: $GPU_NODES"
else
  warn "FAIL: No ${GPU_INSTANCE_TYPE} GPU node found"
  FAILURES=$((FAILURES + 1))
fi

for node in $GPU_NODES; do
  STATUS=$(oc get node "$node" \
    -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null || echo "")
  if [[ "$STATUS" == "True" ]]; then
    ok "GPU node $node is Ready"
  else
    warn "FAIL: GPU node $node NOT Ready (status: ${STATUS:-unknown})"
    FAILURES=$((FAILURES + 1))
  fi
done

# Taint check
check "GPU node has nvidia.com/gpu NoSchedule taint" \
  "oc get nodes -o json | python3 -c \"
import sys,json
d=json.load(sys.stdin)
for n in d['items']:
    taints = n['spec'].get('taints',[])
    if any(t.get('key','')=='nvidia.com/gpu' for t in taints):
        sys.exit(0)
sys.exit(1)
\""

# NFD label check
check "GPU node labeled nvidia.com/gpu.present=true (NFD)" \
  "oc get nodes -l 'nvidia.com/gpu.present=true' --no-headers | grep -q '.'"

# ─────────────────────────────────────────────────────────────────────────────
# PHASE 2 — Cluster Operators (lab_2_operators)
# ─────────────────────────────────────────────────────────────────────────────
step "Phase 2: Cluster Operators — CSV status"

check "Red Hat OpenShift AI (RHOAI) operator Succeeded" \
  "csv_succeeded rhods-operator"

check "NVIDIA GPU Operator Succeeded" \
  "csv_succeeded gpu-operator-certified"

check "Node Feature Discovery (NFD) Succeeded" \
  "csv_succeeded nfd"

check "OpenShift Dev Spaces operator Succeeded" \
  "csv_succeeded devspacesoperator"

check "OpenShift GitOps operator Succeeded" \
  "csv_succeeded openshift-gitops-operator"

check "OpenShift Pipelines operator Succeeded" \
  "csv_succeeded openshift-pipelines-operator"

step "Phase 2b: Operator deployments Available"

check "Dev Spaces operator deployment Available" \
  "oc get deployment devspaces-operator -n openshift-operators \
     -o jsonpath='{.status.availableReplicas}' | grep -qE '[1-9]'"

check "KServe controller deployment Available (RHOAI)" \
  "oc get deployment kserve-controller-manager -n redhat-ods-applications \
     -o jsonpath='{.status.availableReplicas}' | grep -qE '[1-9]'"

check "Tekton pipelines controller deployment Available" \
  "oc get deployment tekton-pipelines-controller -n openshift-pipelines \
     -o jsonpath='{.status.availableReplicas}' | grep -qE '[1-9]'"

check "GitOps ArgoCD server deployment Available (openshift-gitops)" \
  "oc get deployment openshift-gitops-server -n openshift-gitops \
     -o jsonpath='{.status.availableReplicas}' | grep -qE '[1-9]'"

step "Phase 2c: Tekton cluster tasks"

check "buildah Task exists in openshift-pipelines" \
  "oc get task buildah -n openshift-pipelines"

check "git-clone Task exists in openshift-pipelines" \
  "oc get task git-clone -n openshift-pipelines"

# ─────────────────────────────────────────────────────────────────────────────
# PHASE 3 — Platform Instances (lab_4_llm_service Step 1)
# ─────────────────────────────────────────────────────────────────────────────
step "Phase 3: Platform Instances"

# DataScienceCluster
DSC_PHASE=$(oc get datasciencecluster default-dsc \
  -o jsonpath='{.status.phase}' 2>/dev/null || echo "")
if [[ "$DSC_PHASE" == "Ready" ]]; then
  ok "DataScienceCluster default-dsc — Ready"
else
  warn "FAIL: DataScienceCluster not Ready (phase: ${DSC_PHASE:-not found})"
  FAILURES=$((FAILURES + 1))
fi

# DashboardReady is False on ROSA HCP by design (Dashboard not exposed via RHOAI on HCP)
for component in KserveReady ModelControllerReady; do
  COND=$(oc get datasciencecluster default-dsc \
    -o jsonpath="{.status.conditions[?(@.type==\"${component}\")].status}" 2>/dev/null || echo "")
  if [[ "$COND" == "True" ]]; then
    ok "RHOAI $component — True"
  else
    warn "FAIL: RHOAI $component not True (status: ${COND:-not found})"
    FAILURES=$((FAILURES + 1))
  fi
done

# Dev Spaces CheCluster
CHE_PHASE=$(oc get checluster devspaces -n openshift-operators \
  -o jsonpath='{.status.chePhase}' 2>/dev/null || echo "")
if [[ "$CHE_PHASE" == "Active" ]]; then
  ok "Dev Spaces CheCluster — Active"
else
  warn "FAIL: Dev Spaces CheCluster not Active (phase: ${CHE_PHASE:-not found})"
  FAILURES=$((FAILURES + 1))
fi

DEVSPACES_URL=$(oc get checluster devspaces -n openshift-operators \
  -o jsonpath='{.status.cheURL}' 2>/dev/null || echo "")
[[ -n "$DEVSPACES_URL" ]] && ok "Dev Spaces URL available: $DEVSPACES_URL" \
  || { warn "Dev Spaces URL not yet available"; FAILURES=$((FAILURES+1)); }

# NFD NodeFeatureDiscovery
check "NodeFeatureDiscovery nfd-instance exists" \
  "oc get nodefeaturediscovery nfd-instance -n openshift-nfd"

# GPU ClusterPolicy
check "NVIDIA GPU ClusterPolicy exists" \
  "oc get clusterpolicy gpu-cluster-policy"

GPU_POL_STATE=$(oc get clusterpolicy gpu-cluster-policy \
  -o jsonpath='{.status.state}' 2>/dev/null || echo "")
if [[ "$GPU_POL_STATE" == "ready" ]]; then
  ok "GPU ClusterPolicy state — ready"
else
  warn "FAIL: GPU ClusterPolicy not ready (state: ${GPU_POL_STATE:-unknown})"
  FAILURES=$((FAILURES + 1))
fi

# ─────────────────────────────────────────────────────────────────────────────
# PHASE 4 — LLM InferenceService (lab_4_llm_service Step 2)
# ─────────────────────────────────────────────────────────────────────────────
step "Phase 4: LLM InferenceService"

check "llm-inference namespace exists" \
  "oc get namespace $LLM_NS"

check "ServingRuntime vllm-cuda-qwen exists" \
  "oc get servingruntime vllm-cuda-qwen -n $LLM_NS"

check "InferenceService qwen36 exists" \
  "oc get inferenceservice $LLM_IS -n $LLM_NS"

check "Model cache PVC qwen36-model-cache exists" \
  "oc get pvc qwen36-model-cache -n $LLM_NS"

LLM_READY=$(oc get inferenceservice "$LLM_IS" -n "$LLM_NS" \
  -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null || echo "")
if [[ "$LLM_READY" == "True" ]]; then
  ok "InferenceService $LLM_IS — Ready"
else
  warn "FAIL: InferenceService $LLM_IS not Ready (status: ${LLM_READY:-unknown})"
  FAILURES=$((FAILURES + 1))
fi

LLM_PODS=$(oc get pod -n "$LLM_NS" \
  -l "serving.kserve.io/inferenceservice=${LLM_IS}" \
  --field-selector=status.phase=Running \
  --no-headers 2>/dev/null | wc -l || echo 0)
if [[ "$LLM_PODS" -ge 1 ]]; then
  ok "LLM predictor pod running ($LLM_PODS pod(s))"
else
  warn "FAIL: No running LLM predictor pod in $LLM_NS"
  FAILURES=$((FAILURES + 1))
fi

step "Phase 4b: LLM API smoke test (in-cluster)"

# Run a short-lived pod in llm-inference to test the endpoint
info "Launching smoke-test pod in $LLM_NS..."
oc delete pod llm-smoke-test -n "$LLM_NS" --ignore-not-found &>/dev/null || true

oc run llm-smoke-test \
  --image=registry.access.redhat.com/ubi9/python-39:latest \
  --restart=Never \
  --namespace="$LLM_NS" \
  -- sleep 60 &>/dev/null

oc wait pod/llm-smoke-test -n "$LLM_NS" --for=condition=Ready --timeout=60s &>/dev/null || true

LLM_RESP=$(oc exec llm-smoke-test -n "$LLM_NS" -- bash -c "
  curl -sf '${LLM_URL_INTERNAL}/chat/completions' \
    -H 'Content-Type: application/json' \
    -d '{
      \"model\": \"${LLM_IS}\",
      \"messages\": [{\"role\": \"user\", \"content\": \"Reply with exactly: PLATFORM_OK\"}],
      \"max_tokens\": 20,
      \"chat_template_kwargs\": {\"enable_thinking\": false}
    }' | python3 -c \"import sys,json; d=json.load(sys.stdin); print(d['choices'][0]['message']['content'])\"
" 2>/dev/null || echo "")

oc delete pod llm-smoke-test -n "$LLM_NS" --ignore-not-found &>/dev/null || true

if echo "$LLM_RESP" | grep -q "PLATFORM_OK"; then
  ok "LLM API smoke test passed: $LLM_RESP"
else
  warn "FAIL: LLM did not return expected response (got: '${LLM_RESP}')"
  FAILURES=$((FAILURES + 1))
fi

# ─────────────────────────────────────────────────────────────────────────────
# PHASE 5 — Developer Template (lab_5_agents_md)
# ─────────────────────────────────────────────────────────────────────────────
step "Phase 5: Developer Template Repository"

info "Template URL: $TEMPLATE_URL"
check "Template repo reachable on GitHub" \
  "curl -sf --max-time 10 '${TEMPLATE_URL}/archive/main.tar.gz' -o /dev/null"

TMPDIR=$(mktemp -d)
trap "rm -rf $TMPDIR" EXIT

info "Cloning template repository..."
CLONE_OK=0
if git clone --quiet "$TEMPLATE_URL" "$TMPDIR/go-app-template" 2>/dev/null; then
  ok "Template cloned successfully"
  CLONE_OK=1
else
  warn "FAIL: Could not clone template repository"
  FAILURES=$((FAILURES + 1))
fi

if [[ "$CLONE_OK" -eq 1 ]]; then
  REPO="$TMPDIR/go-app-template"

  step "Phase 5a: Template file structure"
  for f in \
    "AGENTS.md" \
    "opencode.json" \
    "devfile.yaml" \
    "README.md" \
    "deploy/base/deployment.yaml" \
    "deploy/base/service.yaml" \
    "deploy/base/route.yaml" \
    "deploy/base/kustomization.yaml" \
    "pipeline/base/pipeline.yaml" \
    "pipeline/base/kustomization.yaml" \
    "gitops/base/argocd.yaml" \
    "gitops/base/kustomization.yaml" \
    "scripts/git-push.yml" \
    "scripts/build-image.yml" \
    "scripts/gitops-deploy.yml"; do
    if [[ -f "$REPO/$f" ]]; then
      ok "Template contains $f"
    else
      warn "FAIL: Template missing $f"
      FAILURES=$((FAILURES + 1))
    fi
  done

  step "Phase 5b: AGENTS.md content"
  for pattern in "main.go" "Dockerfile" "ubi9/go-toolset" "ansible-playbook" "GIT_SERVER"; do
    check "AGENTS.md mentions '$pattern'" \
      "grep -q '$pattern' '$REPO/AGENTS.md'"
  done

  step "Phase 5c: opencode.json"
  check "opencode.json has correct LLM baseURL" \
    "grep -q 'qwen36-predictor.llm-inference' '$REPO/opencode.json'"
  check "opencode.json is valid JSON" \
    "python3 -c \"import json; json.load(open('$REPO/opencode.json'))\""

  step "Phase 5d: devfile.yaml"
  for pattern in "GIT_SERVER" "opencode" "gitpop" "git-push" "build-image" "gitops-deploy"; do
    check "devfile.yaml contains '$pattern'" \
      "grep -q '$pattern' '$REPO/devfile.yaml'"
  done

  step "Phase 5e: Ansible playbooks"
  check "git-push.yml has 'Create repository on Git server'" \
    "grep -q 'Create repository on Git server' '$REPO/scripts/git-push.yml'"
  check "build-image.yml has 'Apply Tekton Pipeline'" \
    "grep -q 'Apply Tekton Pipeline' '$REPO/scripts/build-image.yml'"
  check "gitops-deploy.yml has 'Deploy developer-owned Argo CD'" \
    "grep -q 'Deploy developer-owned Argo CD' '$REPO/scripts/gitops-deploy.yml'"

  step "Phase 5f: Tekton pipeline manifest"
  check "pipeline.yaml references buildah" \
    "grep -q 'buildah' '$REPO/pipeline/base/pipeline.yaml'"
  check "pipeline.yaml has DOCKERFILE parameter" \
    "grep -q 'DOCKERFILE' '$REPO/pipeline/base/pipeline.yaml'"

  step "Phase 5g: ArgoCD manifest"
  check "argocd.yaml is kind ArgoCD" \
    "grep -q 'kind: ArgoCD' '$REPO/gitops/base/argocd.yaml'"

  step "Phase 5h: deployment.yaml uses placeholder image"
  check "deployment.yaml uses 'placeholder' image (updated at runtime by gitops-deploy.yml)" \
    "grep -q 'placeholder' '$REPO/deploy/base/deployment.yaml'"
fi

step "Phase 5i: Git server reachability"
check "Git server is reachable" \
  "curl -sf --max-time 10 '$GIT_SERVER' -o /dev/null"
check "gitpop binary download endpoint is reachable" \
  "curl -sf --max-time 10 '$GIT_SERVER/dl/gitpop?os=linux&arch=amd64' -o /dev/null"

step "Phase 5j: DevSpaces developer launch URL"
if [[ -n "${DEVSPACES_URL:-}" ]]; then
  LAUNCH_URL="${DEVSPACES_URL}/#${TEMPLATE_URL}"
  ok "Developer launch URL constructed:"
  info "$LAUNCH_URL"
else
  warn "DevSpaces URL not available — CheCluster may not be Active"
  FAILURES=$((FAILURES + 1))
fi

# ── Summary ───────────────────────────────────────────────────────────────────
step "Summary"

echo ""
echo -e "  Cluster        : ${CYAN}$(oc whoami --show-server)${NC}"
echo -e "  GPU node(s)    : ${CYAN}${GPU_NODES:-<none found>}${NC}"
echo -e "  LLM endpoint   : ${CYAN}${LLM_URL_INTERNAL}${NC}"
echo -e "  Dev Spaces URL : ${CYAN}${DEVSPACES_URL:-<not ready>}${NC}"
echo -e "  Template repo  : ${CYAN}${TEMPLATE_URL}${NC}"
echo -e "  Git server     : ${CYAN}${GIT_SERVER}${NC}"
if [[ -n "${DEVSPACES_URL:-}" ]]; then
  echo -e "  Developer URL  : ${CYAN}${DEVSPACES_URL}/#${TEMPLATE_URL}${NC}"
fi
echo ""

if [[ $FAILURES -eq 0 ]]; then
  echo -e "${GREEN}${BOLD}All Platform Engineer checks passed ✅${NC}"
else
  echo -e "${RED}${BOLD}$FAILURES check(s) failed — review warnings above ❌${NC}"
  exit 1
fi
