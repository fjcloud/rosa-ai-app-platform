#!/usr/bin/env bash
# Validate the app built in the real workshop; no simulation pod or permission grants.
set -euo pipefail
exec python3 "$(dirname "${BASH_SOURCE[0]}")/check-developer.py"
