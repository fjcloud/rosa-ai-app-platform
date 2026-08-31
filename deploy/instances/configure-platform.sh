#!/usr/bin/env bash
# Post-apply for deploy/instances: Authorino TLS, then dashboard GPU taints + MaaS UI flags.
set -euo pipefail
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
bash "${SCRIPT_DIR}/configure-authorino-tls.sh"
bash "${SCRIPT_DIR}/configure-dashboard.sh"
echo "Platform instances configured (Authorino TLS + dashboard)."
