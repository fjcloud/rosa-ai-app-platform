#!/usr/bin/env bash
# =============================================================================
# Platform Engineer E2E Cleanup — removes all resources created by platform-run.sh
# =============================================================================
# WARNING: This removes cluster-wide operators and platform instances.
#          Do NOT run this on a shared workshop cluster.
# =============================================================================
set -euo pipefail

LLM_NS="${LLM_NS:-llm-inference}"
LLM_IS="${LLM_IS:-qwen36}"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BOLD='\033[1m'
CYAN='\033[0;36m'; NC='\033[0m'

ok()   { echo -e "  ${GREEN}✅  $*${NC}"; }
warn() { echo -e "  ${YELLOW}⚠️   $*${NC}"; }
info() { echo -e "  ${CYAN}→  $*${NC}"; }
step() { echo -e "\n${BOLD}── $* ${NC}"; }

echo -e "${BOLD}=== Platform Engineer E2E Cleanup ===${NC}"
echo -e "${YELLOW}⚠️   This removes operators, LLM, and platform instances from the cluster.${NC}"
echo ""

# ── Safety confirmation ────────────────────────────────────────────────────────
if [[ "${FORCE:-}" != "true" ]]; then
  read -r -p "Are you sure? Type 'yes' to proceed: " CONFIRM
  if [[ "$CONFIRM" != "yes" ]]; then
    echo "Aborted."
    exit 0
  fi
fi

# ─────────────────────────────────────────────────────────────────────────────
# PHASE 1 — LLM InferenceService & namespace
# ─────────────────────────────────────────────────────────────────────────────
step "Phase 1: LLM InferenceService"

# Delete LLM smoke test pod if left behind
oc delete pod llm-smoke-test -n "$LLM_NS" --ignore-not-found &>/dev/null || true

if oc get inferenceservice "$LLM_IS" -n "$LLM_NS" &>/dev/null; then
  oc delete inferenceservice "$LLM_IS" -n "$LLM_NS" --ignore-not-found
  ok "InferenceService $LLM_IS deleted"
fi

if oc get servingruntime vllm-cuda-qwen -n "$LLM_NS" &>/dev/null; then
  oc delete servingruntime vllm-cuda-qwen -n "$LLM_NS" --ignore-not-found
  ok "ServingRuntime vllm-cuda-qwen deleted"
fi

# Delete PVC separately first to avoid stuck namespace (PVC may have finalizers)
if oc get pvc qwen36-model-cache -n "$LLM_NS" &>/dev/null; then
  oc delete pvc qwen36-model-cache -n "$LLM_NS" --ignore-not-found
  ok "PVC qwen36-model-cache deleted"
fi

if oc get namespace "$LLM_NS" &>/dev/null; then
  oc delete namespace "$LLM_NS" --ignore-not-found
  ok "Namespace $LLM_NS deleted"
else
  info "Namespace $LLM_NS already absent"
fi

# ─────────────────────────────────────────────────────────────────────────────
# PHASE 2 — Platform instances (DataScienceCluster, CheCluster, NFD, GPU)
# ─────────────────────────────────────────────────────────────────────────────
step "Phase 2: Platform instances"

if oc get datasciencecluster default-dsc &>/dev/null; then
  oc delete datasciencecluster default-dsc --ignore-not-found
  ok "DataScienceCluster default-dsc deleted"
fi

if oc get dscinitialization default-dsci &>/dev/null; then
  oc delete dscinitialization default-dsci --ignore-not-found
  ok "DSCInitialization default-dsci deleted"
fi

if oc get checluster devspaces -n openshift-operators &>/dev/null; then
  oc delete checluster devspaces -n openshift-operators --ignore-not-found
  ok "CheCluster devspaces deleted"
fi

if oc get nodefeaturediscovery nfd-instance -n openshift-nfd &>/dev/null; then
  oc delete nodefeaturediscovery nfd-instance -n openshift-nfd --ignore-not-found
  ok "NodeFeatureDiscovery nfd-instance deleted"
fi

if oc get clusterpolicy gpu-cluster-policy &>/dev/null; then
  oc delete clusterpolicy gpu-cluster-policy --ignore-not-found
  ok "GPU ClusterPolicy deleted"
fi

# ─────────────────────────────────────────────────────────────────────────────
# PHASE 3 — Operator subscriptions & namespaces
# ─────────────────────────────────────────────────────────────────────────────
step "Phase 3: Operators (subscriptions, CSVs, namespaces)"

# RHOAI
if oc get subscription rhods-operator -n redhat-ods-operator &>/dev/null; then
  oc delete subscription rhods-operator -n redhat-ods-operator --ignore-not-found
  ok "RHOAI subscription deleted"
fi

# NFD
if oc get subscription nfd -n openshift-nfd &>/dev/null; then
  oc delete subscription nfd -n openshift-nfd --ignore-not-found
  ok "NFD subscription deleted"
fi

# GPU Operator
if oc get subscription gpu-operator-certified -n nvidia-gpu-operator &>/dev/null; then
  oc delete subscription gpu-operator-certified -n nvidia-gpu-operator --ignore-not-found
  ok "GPU Operator subscription deleted"
fi

# Dev Spaces
if oc get subscription devspaces -n openshift-operators &>/dev/null; then
  oc delete subscription devspaces -n openshift-operators --ignore-not-found
  ok "Dev Spaces subscription deleted"
fi

# GitOps
if oc get subscription openshift-gitops-operator -n openshift-gitops-operator &>/dev/null; then
  oc delete subscription openshift-gitops-operator -n openshift-gitops-operator --ignore-not-found
  ok "GitOps subscription deleted"
fi

# Pipelines
if oc get subscription openshift-pipelines-operator-rh -n openshift-operators &>/dev/null; then
  oc delete subscription openshift-pipelines-operator-rh -n openshift-operators --ignore-not-found
  ok "Pipelines subscription deleted"
fi

# Operator namespaces (will also remove CSVs and operator pods)
for ns in redhat-ods-operator openshift-nfd nvidia-gpu-operator \
           openshift-gitops-operator openshift-pipelines openshift-gitops \
           openshift-devspaces redhat-ods-applications; do
  if oc get namespace "$ns" &>/dev/null; then
    info "Deleting namespace $ns (this may take a moment)..."
    oc delete namespace "$ns" --ignore-not-found --wait=false
    ok "Namespace $ns deletion triggered"
  else
    info "Namespace $ns already absent"
  fi
done

# ─────────────────────────────────────────────────────────────────────────────
# PHASE 4 — DCGM dashboard ConfigMap
# ─────────────────────────────────────────────────────────────────────────────
step "Phase 4: Monitoring resources"

oc delete configmap nvidia-dcgm-exporter-dashboard \
  -n openshift-config-managed --ignore-not-found 2>/dev/null || true
ok "DCGM dashboard ConfigMap removed (if present)"

# ─────────────────────────────────────────────────────────────────────────────
# PHASE 5 — Local temp files
# ─────────────────────────────────────────────────────────────────────────────
step "Phase 5: Local temp files"

rm -rf /tmp/go-app-template
ok "Local temp files removed"

echo ""
echo -e "${GREEN}${BOLD}Platform e2e cleanup complete.${NC}"
echo -e "  Run ${BOLD}bash e2e/platform-run.sh${NC} to validate a fresh setup."
