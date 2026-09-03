#!/usr/bin/env bash
# Post-apply for deploy/instances: free CPU for Dev Spaces, Authorino TLS,
# bind MaaS Gateway to this cluster (apps domain +
# <infrastructureName>-primary-cert-bundle-secret), recycle Kuadrant after
# Gateway API CRDs exist, then dashboard GPU taints + MaaS UI flags.
set -euo pipefail
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
bash "${SCRIPT_DIR}/configure-lws-cpu.sh"
bash "${SCRIPT_DIR}/configure-authorino-tls.sh"
bash "${SCRIPT_DIR}/configure-maas-gateway.sh"
bash "${SCRIPT_DIR}/configure-kuadrant-gateway.sh"
bash "${SCRIPT_DIR}/configure-dashboard.sh"
echo "Platform instances configured (LWS CPU + Authorino TLS + MaaS Gateway + Kuadrant + dashboard)."
