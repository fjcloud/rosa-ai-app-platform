#!/usr/bin/env bash
# Facilitator-only: add a private worker subnet when another AZ has GPU capacity.
set -euo pipefail
export AWS_PAGER=''

zone=${1:?Usage: bash scripts/prepare-gpu-subnet.sh <availability-zone>}
cluster=$(oc get infrastructure cluster -o jsonpath='{.status.infrastructureName}')
region=$(oc get infrastructure cluster -o jsonpath='{.status.platformStatus.aws.region}')
[[ "$zone" == "$region"[a-z] ]] || { echo 'Choose a zone in the cluster region.' >&2; exit 1; }
rosa describe cluster --cluster "$cluster" -o json | jq -e '.hypershift.enabled == true' >/dev/null || {
  echo 'This helper requires an existing ROSA HCP cluster.' >&2
  exit 1
}

worker=$(rosa list machinepools --cluster "$cluster" -o json | jq -er '[.[] | select(.id != "gpu")][0].subnet')
vpc=$(aws ec2 describe-subnets --region "$region" --subnet-ids "$worker" --query 'Subnets[0].VpcId' --output text)
routes=$(aws ec2 describe-route-tables --region "$region" --filters "Name=association.subnet-id,Values=$worker" --output json)
route=$(jq -er '.RouteTables[0] | select(any(.Routes[]; .DestinationCidrBlock == "0.0.0.0/0" and .NatGatewayId != null and .State == "active")) | .RouteTableId' <<< "$routes") || {
  echo 'No explicit private worker route table with an active NAT route was found. Ask the facilitator to prepare the network.' >&2
  exit 1
}

existing=$(aws ec2 describe-subnets --region "$region" --filters "Name=vpc-id,Values=$vpc" "Name=availability-zone,Values=$zone" "Name=tag:cloud-terminal/gpu-cluster,Values=$cluster" --query 'Subnets[].SubnetId' --output text)
if [[ -n "$existing" ]]; then
  [[ "$existing" != *$'\t'* ]] || { echo 'Multiple GPU subnets found; ask the facilitator to select one.' >&2; exit 1; }
  printf '%s\n' "$existing"
  exit 0
fi

aws ec2 describe-instance-type-offerings --region "$region" --location-type availability-zone \
  --filters Name=instance-type,Values=g6e.xlarge "Name=location,Values=$zone" \
  --output json | jq -e '.InstanceTypeOfferings | length > 0' >/dev/null || {
  echo "g6e.xlarge is not offered in $zone. Choose another zone in $region." >&2
  exit 1
}

vpc_cidr=$(aws ec2 describe-vpcs --region "$region" --vpc-ids "$vpc" --query 'Vpcs[0].CidrBlock' --output text)
used=$(aws ec2 describe-subnets --region "$region" --filters "Name=vpc-id,Values=$vpc" --query 'Subnets[].CidrBlock' --output json)
cidr=$(python3 -c '
import ipaddress,json,sys
vpc=ipaddress.ip_network(sys.argv[1])
used=[ipaddress.ip_network(c) for c in json.loads(sys.argv[2])]
if vpc.prefixlen > 24: sys.exit("The VPC has no free /24 subnet; ask the facilitator.")
for subnet in vpc.subnets(new_prefix=24):
    if not any(subnet.overlaps(other) for other in used):
        print(subnet)
        break
else: sys.exit("The VPC has no free /24 subnet; ask the facilitator.")
' "$vpc_cidr" "$used")

created=''
trap 'result=$?; if ((result != 0)) && [[ -n "$created" ]]; then aws ec2 delete-subnet --region "$region" --subnet-id "$created" >&2 || true; fi' EXIT
created=$(aws ec2 create-subnet --region "$region" --vpc-id "$vpc" --availability-zone "$zone" --cidr-block "$cidr" \
  --tag-specifications "ResourceType=subnet,Tags=[{Key=Name,Value=workshop-gpu-$zone},{Key=cloud-terminal/gpu-cluster,Value=$cluster},{Key=kubernetes.io/cluster/$cluster,Value=shared}]" \
  --query 'Subnet.SubnetId' --output text)
aws ec2 wait subnet-available --region "$region" --subnet-ids "$created"
aws ec2 associate-route-table --region "$region" --subnet-id "$created" --route-table-id "$route" >/dev/null
printf '%s\n' "$created"
