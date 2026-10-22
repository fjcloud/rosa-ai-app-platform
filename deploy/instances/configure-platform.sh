#!/usr/bin/env bash
# Bind platform instances to the current cluster after their operators reconcile.
set -euo pipefail
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

wait_resource() {
  local ns=$1 resource=$2 deadline=$((SECONDS + 600))
  echo "Waiting for ${resource} in ${ns}..."
  until oc --request-timeout=15s get "$resource" -n "$ns" >/dev/null 2>&1; do
    if (( SECONDS >= deadline )); then
      echo "Timed out waiting for ${resource}. Check pods in ${ns}." >&2
      exit 1
    fi
    sleep 5
  done
}

bash "${SCRIPT_DIR}/configure-maas-gateway.sh"
wait_resource kuadrant-system authorino/authorino
wait_resource kuadrant-system service/authorino-authorino-authorization
wait_resource kuadrant-system deployment/authorino
bash "${SCRIPT_DIR}/configure-authorino-tls.sh"
bash "${SCRIPT_DIR}/configure-kuadrant-gateway.sh"
bash "${SCRIPT_DIR}/configure-dashboard.sh"
echo "Platform instances configured (Authorino TLS + MaaS Gateway + Kuadrant + dashboard)."
