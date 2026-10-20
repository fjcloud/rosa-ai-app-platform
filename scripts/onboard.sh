#!/usr/bin/env bash
# Validate the shell before any cluster resources are created.
set -euo pipefail
if [[ -s "${HOME}/.rhcs.env" ]]; then
  set -a
  source "${HOME}/.rhcs.env"
  set +a
fi
if command -v workshop-tools >/dev/null 2>&1; then
  workshop-tools check aws
else
  for tool in aws rosa git make oc; do
    command -v "$tool" >/dev/null || { echo "Missing $tool. Start a new Cloud Terminal." >&2; exit 1; }
  done
  [[ -n "${AWS_SECRET_ACCESS_KEY:-}" ]] || { echo 'Lab AWS credentials are missing. Start Cloud Terminal again.' >&2; exit 1; }
  aws sts get-caller-identity >/dev/null
  rosa whoami >/dev/null
fi
[[ -n "${RHCS_CLIENT_ID:-}" && -n "${RHCS_CLIENT_SECRET:-}" ]] || {
  echo 'Red Hat service account is missing. Start Cloud Terminal again, or export RHCS_CLIENT_ID and RHCS_CLIENT_SECRET.' >&2
  exit 1
}
echo "Ready to create a ROSA cluster in ${AWS_DEFAULT_REGION:-the configured AWS region}. No cluster resources were created."
