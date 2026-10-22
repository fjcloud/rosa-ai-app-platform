#!/usr/bin/env bash
# Validate an existing workshop environment without changing cloud or cluster resources.
set -euo pipefail
for tool in oc aws rosa git jq python3 curl; do
  command -v "$tool" >/dev/null 2>&1 || { echo "Missing $tool. Ask the facilitator to prepare the RHDP bastion." >&2; exit 1; }
done
aws sts get-caller-identity >/dev/null
rosa whoami >/dev/null
oc whoami >/dev/null 2>&1 || {
  echo 'Log in to the existing cluster using the RHDP access details or the console Copy login command.' >&2
  exit 1
}
[[ "$(oc auth can-i '*' '*' --all-namespaces)" == yes ]] || {
  echo 'The platform labs require cluster-admin access. Ask the facilitator for the assigned administrator login.' >&2
  exit 1
}
oc get nodes -o json | python3 -c '
import json,sys
nodes=json.load(sys.stdin).get("items",[])
workers=[n for n in nodes if "node-role.kubernetes.io/worker" in n.get("metadata",{}).get("labels",{})]
if not workers: sys.exit("No worker nodes found. Ask the facilitator to check the existing cluster.")
if any(not any(c.get("type")=="Ready" and c.get("status")=="True" for c in n.get("status",{}).get("conditions",[])) for n in workers):
    sys.exit("Workers are not all Ready. Wait or ask the facilitator before continuing.")
cpu_workers=[n for n in workers if not n.get("spec",{}).get("unschedulable") and not any(t.get("key")=="nvidia.com/gpu" for t in n.get("spec",{}).get("taints",[]))]
def millicores(n):
    v=n.get("status",{}).get("allocatable",{}).get("cpu","0")
    return int(v[:-1]) if v.endswith("m") else int(float(v)*1000)
cpu=sum(millicores(n) for n in cpu_workers)
if cpu < 17500:
    sys.exit("Insufficient CPU worker capacity: "+str(cpu/1000)+" allocatable cores. Ask the facilitator for five m6a.xlarge CPU workers (or at least 17.5 allocatable CPU cores), plus the GPU pool.")
print("Existing cluster access verified; workers are Ready; CPU capacity:",cpu/1000,"cores.")'
oc get clusterversion version -o json | python3 -c '
import json,re,sys
version=json.load(sys.stdin).get("status",{}).get("desired",{}).get("version","")
m=re.match(r"^(\d+)\.(\d+)\.",version)
if not m or tuple(map(int,m.groups())) < (4,22):
    sys.exit("This guide targets OpenShift 4.22 or later; the existing cluster reports "+(version or "an unknown version")+". Ask the facilitator for a compatible RHDP environment before Act 1.")
print("OpenShift version:",version)'
echo 'Ready for Act 1. No cluster, identity, or billing resources were created.'
