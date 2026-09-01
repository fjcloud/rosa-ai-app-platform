#!/usr/bin/env bash
# Post-apply for deploy/instances: Authorino TLS, bind MaaS Gateway to this
# cluster (apps domain + <infrastructureName>-primary-cert-bundle-secret),
# then dashboard GPU taints + MaaS UI flags.
set -euo pipefail
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
bash "${SCRIPT_DIR}/configure-authorino-tls.sh"
bash "${SCRIPT_DIR}/configure-maas-gateway.sh"
bash "${SCRIPT_DIR}/configure-dashboard.sh"
echo "Platform instances configured (Authorino TLS + MaaS Gateway + dashboard)."
