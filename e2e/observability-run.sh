#!/usr/bin/env bash
# Act 3: query the same GPU and vLLM metrics shown in the OpenShift console.
set -euo pipefail
python3 <<'PY'
import json, subprocess, urllib.parse, urllib.request

def oc(*args):
    return subprocess.check_output(['oc', *args], text=True).strip()

host = oc('get', 'route', 'thanos-querier', '-n', 'openshift-monitoring', '-o', 'jsonpath={.spec.host}')
token = oc('whoami', '-t')
queries = [
    'DCGM_FI_DEV_GPU_UTIL',
    'DCGM_FI_DEV_FB_USED',
    'DCGM_FI_DEV_GPU_TEMP',
    'DCGM_FI_DEV_POWER_USAGE',
    'vllm:generation_tokens_total{namespace="llm-serving"}',
    'vllm:prompt_tokens_total{namespace="llm-serving"}',
    'vllm:time_to_first_token_seconds_bucket{namespace="llm-serving"}',
    'vllm:num_requests_running{namespace="llm-serving"}',
    'vllm:num_requests_waiting{namespace="llm-serving"}',
]
failures = []
for query in queries:
    url = 'https://' + host + '/api/v1/query?' + urllib.parse.urlencode({'query': query})
    request = urllib.request.Request(url, headers={'Authorization': 'Bearer ' + token})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.load(response)
        rows = data.get('data', {}).get('result', [])
        assert data.get('status') == 'success' and rows, 'no series returned'
        if 'tokens_total' in query:
            assert sum(float(row['value'][1]) for row in rows) > 0, 'no tokens recorded'
        print('PASS:', query, '(' + str(len(rows)) + ' series)')
    except Exception as error:
        print('FAIL:', query, '(' + type(error).__name__ + ')')
        failures.append(query)

cm = json.loads(oc('get', 'configmap', 'nvidia-dcgm-exporter-dashboard', '-n', 'openshift-config-managed', '-o', 'json'))
dashboard = json.loads(cm['data']['dcgm-exporter-dashboard.json'])
assert dashboard.get('panels'), 'DCGM dashboard has no panels'
subscription = json.loads(oc('get', 'maassubscription', 'qwen3-workshop', '-n', 'models-as-a-service', '-o', 'json'))
assert subscription['status']['phase'] == 'Active', 'MaaS subscription is not Active'
assert any(limit['limit'] == 5000000 and limit['window'] == '24h'
           for ref in subscription['spec']['modelRefs'] for limit in ref['tokenRateLimits']), 'workshop quota differs'
policy = json.loads(oc('get', 'tokenratelimitpolicy', 'maas-trlp-qwen3', '-n', 'llm-serving', '-o', 'json'))
conditions = {c['type']: c['status'] for c in policy['status']['conditions']}
assert conditions.get('Accepted') == 'True' and conditions.get('Enforced') == 'True', 'token quota policy is not enforced'
print('PASS: DCGM dashboard and enforced 5M tokens / 24h subscription')
if failures:
    raise SystemExit(str(len(failures)) + ' metric checks failed')
print('Act 3 observability checks passed.')
PY
