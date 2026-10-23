#!/usr/bin/env bash
# Check the cluster version before installing the workshop's 4.22 Gateway API stack.
set -euo pipefail
oc --request-timeout=30s get clusterversion version -o json | python3 -c '
import json,re,sys
status=json.load(sys.stdin).get("status",{})
desired=status.get("desired",{}).get("version","")
current=next((h.get("version","") for h in status.get("history",[]) if h.get("state")=="Completed"),"")
match=re.match(r"^(\d+)\.(\d+)\.",current)
if not match or tuple(map(int,match.groups())) < (4,22):
    sys.exit("Stop: this workshop uses the OpenShift 4.22 Gateway API path for MaaS. Completed cluster version: "+(current or "unknown")+"; target: "+(desired or "unknown")+". Ask the facilitator to prepare a compatible cluster before installing operators. A 4.19 patch update is not sufficient.")
if current != desired or any(c.get("type")=="Progressing" and c.get("status")=="True" for c in status.get("conditions",[])):
    sys.exit("Cluster update in progress ("+current+" -> "+desired+"). Wait for completion before continuing.")
print("OpenShift version:",current)'
