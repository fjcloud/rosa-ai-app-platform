#!/usr/bin/env python3
"""Read-only checks for the application built in the real ROSA workshop workspace."""
import html
import json
import os
import subprocess
import sys
import urllib.request


def oc(*args):
    return subprocess.check_output(['oc', *args], text=True, stderr=subprocess.DEVNULL, timeout=45).strip()


def resource(kind, name, namespace=None):
    args = ['get', kind, name, '-o', 'json']
    if namespace:
        args += ['-n', namespace]
    return json.loads(oc(*args))


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print('PASS:', message, flush=True)


def developer():
    app = os.environ.get('APP_NAME', 'fortune-cookie')
    ns = app + '-dev'
    deployment = resource('deployment', app, ns)
    require(deployment.get('status', {}).get('availableReplicas', 0) >= 1, 'Application available')
    application = resource('application', app, ns)
    require(application.get('status', {}).get('sync', {}).get('status') == 'Synced' and application.get('status', {}).get('health', {}).get('status') == 'Healthy', 'Personal Argo CD Application Synced / Healthy')
    runs = json.loads(oc('get', 'pipelineruns', '-n', app + '-build', '-o', 'json'))['items']
    require(bool(runs), 'Real Tekton PipelineRuns exist')
    latest = max(runs, key=lambda r: r['metadata']['creationTimestamp'])
    require(any(c['type'] == 'Succeeded' and c['status'] == 'True' for c in latest.get('status', {}).get('conditions', [])), 'Latest Tekton build Succeeded')
    route = resource('route', app, ns)
    require(route['spec'].get('tls', {}).get('termination') == 'edge' and route['spec']['tls'].get('insecureEdgeTerminationPolicy') == 'Redirect', 'HTTPS edge Route redirects HTTP')
    url = 'https://' + route['spec']['host']
    with urllib.request.urlopen(url + '/healthz', timeout=30) as response:
        require(json.load(response) == {'status': 'ok'}, 'Public HTTPS health endpoint')
    with urllib.request.urlopen(url, timeout=30) as response:
        page = response.read().decode('utf-8')
    require(any(word in page.lower() for word in ('fortune', 'cookie', 'luck', 'wisdom')), 'Public page renders the Fortune Cookie application')
    if os.environ.get('EXPECT_UPDATED_APP') == 'true':
        require('🥠' in html.unescape(page), 'Shipped update contains the fortune-cookie emoji')
    spec = deployment['spec']['template']['spec']
    container = spec['containers'][0]
    expected_image = f'image-registry.openshift-image-registry.svc:5000/{app}-build/{app}:latest'
    require(container.get('image') == expected_image, 'Deployment uses the app image from its build namespace')
    require(container.get('imagePullPolicy') == 'Always', 'Mutable latest tag is always pulled')
    requested_image = next((p['value'] for p in latest['spec'].get('params', []) if p['name'] == 'image'), expected_image)
    require(requested_image == container['image'], 'Successful Tekton target matches the deployed image')
    resources = container.get('resources', {})
    require(resources.get('requests') == {'cpu': '50m', 'memory': '64Mi'} and resources.get('limits') == {'cpu': '200m', 'memory': '128Mi'}, 'Resource requests and limits match AGENTS.md')
    require(all(container.get(probe, {}).get('httpGet', {}).get('path') == '/healthz' and container[probe]['httpGet'].get('port') == 8080 for probe in ['livenessProbe', 'readinessProbe']), 'Liveness and readiness probes use /healthz:8080')
    security = spec.get('securityContext', {})
    require(security.get('runAsNonRoot') is True and security.get('seccompProfile', {}).get('type') == 'RuntimeDefault' and 'runAsUser' not in security, 'Deployment uses portable restricted pod security')
    cs = container.get('securityContext', {})
    require(cs.get('allowPrivilegeEscalation') is False and 'ALL' in cs.get('capabilities', {}).get('drop', []), 'Container drops all capabilities and privilege escalation')
    pods = json.loads(oc('get', 'pods', '-n', ns, '-l', 'app.kubernetes.io/name=' + app, '-o', 'json'))['items']
    require(bool(pods) and all(p['metadata'].get('annotations', {}).get('openshift.io/scc') == 'restricted-v2' for p in pods), 'Application admitted under restricted-v2 SCC')
    build_pods = json.loads(oc('get', 'pods', '-n', app + '-build', '-l', 'tekton.dev/pipelineRun=' + latest['metadata']['name'], '-o', 'json'))['items']
    require(bool(build_pods) and all(p['spec'].get('hostUsers') is False for p in build_pods), 'Build tasks isolated in Linux user namespaces')
    require(all(not c.get('securityContext', {}).get('privileged', False) and c.get('securityContext', {}).get('allowPrivilegeEscalation') is False for p in build_pods for c in p['spec'].get('containers', []) + p['spec'].get('initContainers', [])), 'No privileged build container or privilege escalation')
    require(any(c.get('ready') and '@sha256:' in c.get('imageID', '') for p in pods for c in p.get('status', {}).get('containerStatuses', [])), 'Running application pulled a built image digest')
    workspace_ns, workspace_pod = os.environ.get('E2E_NS'), os.environ.get('DEV_POD')
    if workspace_ns or workspace_pod:
        require(bool(workspace_ns and workspace_pod), 'Both E2E_NS and DEV_POD supplied')
        prefix = ['exec', workspace_pod, '-n', workspace_ns, '-c', os.environ.get('DEV_CONTAINER', 'dev'), '--', 'bash', '-c']
        oc(*prefix, 'cd "$PROJECT_SOURCE" && test -f main.go && test -f go.mod && test -f Dockerfile && CGO_ENABLED=0 go build -buildvcs=false -o /dev/null .')
        print('PASS: Generated source files exist and Go build succeeds in the real workspace')
        head = oc(*prefix, 'cd "$PROJECT_SOURCE" && git rev-parse HEAD')
        remote = oc(*prefix, 'cd "$PROJECT_SOURCE" && git ls-remote origin refs/heads/main').split()[0]
        require(head == remote == application['status']['sync'].get('revision'), 'Workspace commit, pushed main and Argo CD revision match')
        oc(*prefix, 'cd "$PROJECT_SOURCE" && git diff --exit-code && git cat-file -e HEAD:main.go')
        print('PASS: Application source committed with no unstaged changes')
    print('Application:', url)
    print('Git revision:', application['status']['sync'].get('revision', 'unknown'))


if __name__ == '__main__':
    try:
        developer()
    except AssertionError as error:
        sys.exit('FAIL: ' + str(error))
    except Exception as error:
        # Never print tokens, Secret data, subprocess output or HTTP error bodies.
        sys.exit('FAIL: ' + type(error).__name__ + '. Check the selected cluster, workspace and application.')
