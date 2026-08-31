#!/usr/bin/env bash
# Mint a MaaS API key bound to qwen3-workshop and store it as OPENAI_API_KEY
# for Dev Spaces (OpenCode / Continue). Requires cluster-admin (or any user
# in a group listed on MaaSSubscription/qwen3-workshop).
set -euo pipefail

SECRET_NS="${SECRET_NS:-openshift-operators}"
SECRET_NAME="${SECRET_NAME:-ai-provider-openai-api-key}"
SUBSCRIPTION="${SUBSCRIPTION:-qwen3-workshop}"
KEY_NAME="${KEY_NAME:-workshop-opencode}"

MAAS_HOST="${MAAS_HOST:-maas.$(oc get ingresses.config.openshift.io cluster -o jsonpath='{.spec.domain}')}"
MAAS_API_URL="https://${MAAS_HOST}"

echo "Minting MaaS key '${KEY_NAME}' on ${MAAS_API_URL} (subscription=${SUBSCRIPTION})"

RESP="$(curl -sS -w '\n%{http_code}' -X POST "${MAAS_API_URL}/maas-api/v1/api-keys" \
  -H "Authorization: Bearer $(oc whoami -t)" \
  -H "Content-Type: application/json" \
  -d "{\"name\": \"${KEY_NAME}\", \"description\": \"Dev Spaces OpenCode workshop key\", \"subscription\": \"${SUBSCRIPTION}\", \"expiresIn\": \"90d\"}")"

HTTP_CODE="$(echo "${RESP}" | tail -n1)"
BODY="$(echo "${RESP}" | sed '$d')"

if [[ "${HTTP_CODE}" != "200" && "${HTTP_CODE}" != "201" ]]; then
  echo "Failed to mint API key (HTTP ${HTTP_CODE}):" >&2
  echo "${BODY}" >&2
  exit 1
fi

API_KEY="$(echo "${BODY}" | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d.get("key") or "")')"
if [[ -z "${API_KEY}" || "${API_KEY}" != sk-oai-* ]]; then
  echo "Mint response did not include a sk-oai- key:" >&2
  echo "${BODY}" >&2
  exit 1
fi

oc create secret generic "${SECRET_NAME}" \
  -n "${SECRET_NS}" \
  --from-literal=OPENAI_API_KEY="${API_KEY}" \
  --dry-run=client -o yaml | oc apply -f -

# Restore Che injector labels after apply
oc label secret "${SECRET_NAME}" -n "${SECRET_NS}" \
  app.kubernetes.io/part-of=che.eclipse.org \
  app.kubernetes.io/component=workspaces-config \
  controller.devfile.io/mount-to-devworkspace=true \
  controller.devfile.io/watch-secret=true \
  che.eclipse.org/ai-provider-id=opencodeai-opencode \
  --overwrite >/dev/null
oc annotate secret "${SECRET_NAME}" -n "${SECRET_NS}" \
  controller.devfile.io/mount-as=env \
  controller.devfile.io/mount-on-start=true \
  --overwrite >/dev/null

echo "Stored key prefix ${API_KEY:0:12}... in secret/${SECRET_NAME} (${SECRET_NS})"
echo "Smoke: curl -sS ${MAAS_API_URL}/v1/models -H 'Authorization: Bearer \$OPENAI_API_KEY'"
