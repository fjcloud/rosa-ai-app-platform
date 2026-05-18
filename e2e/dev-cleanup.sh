#!/usr/bin/env bash
# =============================================================================
# Developer E2E Cleanup — removes all resources created by run.sh
# =============================================================================
set -euo pipefail

APP_NAME="${APP_NAME:-fortune-cookie}"
E2E_NS="${E2E_NS:-workshop-e2e}"
GIT_SERVER="${GIT_SERVER:-https://gitpop.apps.sno.msl.cloud}"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BOLD='\033[1m'; NC='\033[0m'

ok()   { echo -e "  ${GREEN}✅  $*${NC}"; }
warn() { echo -e "  ${YELLOW}⚠️   $*${NC}"; }
info() { echo -e "  → $*"; }

echo -e "${BOLD}=== Developer E2E Cleanup ===${NC}"
info "APP_NAME: $APP_NAME"
info "E2E_NS:   $E2E_NS"
echo ""

# ── Argo CD Application & instance (developer-owned, in APP-dev namespace) ────
if oc get application "$APP_NAME" -n "${APP_NAME}-dev" &>/dev/null; then
  oc delete application "$APP_NAME" -n "${APP_NAME}-dev" --ignore-not-found
  ok "ArgoCD Application '$APP_NAME' deleted from ${APP_NAME}-dev"
fi

if oc get argocd argocd -n "${APP_NAME}-dev" &>/dev/null; then
  oc delete argocd argocd -n "${APP_NAME}-dev" --ignore-not-found
  ok "ArgoCD instance deleted from ${APP_NAME}-dev"
fi

# ── App namespaces ─────────────────────────────────────────────────────────────
for ns in "${APP_NAME}-build" "${APP_NAME}-dev" "$E2E_NS"; do
  if oc get namespace "$ns" &>/dev/null; then
    oc delete namespace "$ns" --ignore-not-found
    ok "Namespace $ns deleted"
  else
    info "Namespace $ns already absent"
  fi
done

# ── Git server repos (gitpop — delete via wallet token) ───────────────────────
GITPOP_BIN="/tmp/gitpop-e2e"
if [[ ! -x "$GITPOP_BIN" ]]; then
  info "Downloading gitpop to delete Git server repos..."
  curl -fsSL "${GIT_SERVER}/dl/gitpop?os=linux&arch=amd64" -o "$GITPOP_BIN" 2>/dev/null \
    && chmod +x "$GITPOP_BIN" || true
fi

if [[ -x "$GITPOP_BIN" ]]; then
  # gitpop repo delete reads the wallet from .git/gitpop/ in the repo dir
  # We don't have the wallet here, so we skip silently — gitpop repos are ephemeral
  info "Git server repos are ephemeral and expire automatically (gitpop)"
  info "To delete manually: gitpop repo delete --repo <url>"
fi

# ── Local temp files ───────────────────────────────────────────────────────────
rm -f "$GITPOP_BIN"
rm -rf /tmp/go-app-template /tmp/opencode-build.log \
       /tmp/deploy-git.log /tmp/deploy-build.log /tmp/deploy-gitops.log

ok "Local temp files removed"

echo ""
echo -e "${GREEN}${BOLD}Developer e2e cleanup complete.${NC}"
echo -e "  Run ${BOLD}bash e2e/run.sh${NC} to start fresh."
