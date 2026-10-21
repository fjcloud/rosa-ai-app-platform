#!/usr/bin/env bash
# Wait for a GPU worker to appear and become Ready, within one 20-minute budget.
set -euo pipefail

selector='node.kubernetes.io/instance-type=g6e.xlarge'
deadline=$((SECONDS + 1200))

echo 'Waiting up to 20 minutes for the GPU worker to become Ready...'
while true; do
  nodes=$(oc get nodes -l "$selector" -o name --request-timeout=30s)
  remaining=$((deadline - SECONDS))
  if ((remaining <= 0)); then
    echo 'GPU worker timed out. Check the gpu machine pool, AWS quota, and capacity with your facilitator.' >&2
    exit 1
  fi
  if [[ -n "$nodes" ]]; then
    break
  fi
  sleep 10
done

oc wait node -l "$selector" --for=condition=Ready --timeout="${remaining}s"
