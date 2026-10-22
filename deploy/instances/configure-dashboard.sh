#!/usr/bin/env bash
# Enable MaaS / Gen AI studio flags through the supported dashboard configuration.
set -euo pipefail

NS=redhat-ods-applications
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

echo "Waiting for OdhDashboardConfig..."
for _ in $(seq 1 36); do
  if oc get odhdashboardconfig odh-dashboard-config -n "$NS" >/dev/null 2>&1; then
    break
  fi
  sleep 5
done

# Merge only supported flags. oc apply on the full CR trips CEL rules for
# deprecated keys and notebookNamespace immutability.
oc patch odhdashboardconfig odh-dashboard-config -n "$NS" --type=merge --patch-file="${SCRIPT_DIR}/odh-dashboard-config.yaml"

echo "Dashboard MaaS UI flags applied."
