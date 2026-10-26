"""Reject regressions in the real-workspace delivery checker without a cluster."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('developer', Path(__file__).with_name('check-developer.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
IMAGE = 'image-registry.openshift-image-registry.svc:5000/fortune-cookie-build/fortune-cookie:latest'


class DeveloperValidation(unittest.TestCase):
    def setUp(self):
        container = {'image': IMAGE, 'imagePullPolicy': 'Always',
                     'resources': {'requests': {'cpu': '50m', 'memory': '64Mi'}, 'limits': {'cpu': '200m', 'memory': '128Mi'}},
                     'readinessProbe': {'httpGet': {'path': '/healthz', 'port': 8080}},
                     'livenessProbe': {'httpGet': {'path': '/healthz', 'port': 8080}},
                     'securityContext': {'allowPrivilegeEscalation': False, 'capabilities': {'drop': ['ALL']}}}
        self.deployment = {'status': {'availableReplicas': 1}, 'spec': {'template': {'spec': {
            'securityContext': {'runAsNonRoot': True, 'seccompProfile': {'type': 'RuntimeDefault'}}, 'containers': [container]}}}}
        self.application = {'status': {'sync': {'status': 'Synced', 'revision': 'tested-revision'}, 'health': {'status': 'Healthy'}}}
        self.route = {'spec': {'host': 'app.example.test', 'tls': {'termination': 'edge', 'insecureEdgeTerminationPolicy': 'Redirect'}}}
        self.run = {'metadata': {'name': 'build-new', 'creationTimestamp': '2026-10-26T12:00:00Z'},
                    'status': {'conditions': [{'type': 'Succeeded', 'status': 'True'}]},
                    'spec': {'params': [{'name': 'image', 'value': IMAGE}]}}
        self.app_pod = {'metadata': {'annotations': {'openshift.io/scc': 'restricted-v2'}},
                        'status': {'containerStatuses': [{'ready': True, 'imageID': IMAGE + '@sha256:abc'}]}}
        self.build_pod = {'spec': {'hostUsers': False, 'containers': [{'securityContext': {'allowPrivilegeEscalation': False}}]}}
        self.runs = [self.run]

    def check(self):
        def resource(kind, *args):
            return {'deployment': self.deployment, 'application': self.application, 'route': self.route}[kind]
        def oc(*args):
            if args[:2] == ('get', 'pipelineruns'):
                return json.dumps({'items': self.runs})
            if args[:2] == ('get', 'pods'):
                return json.dumps({'items': [self.build_pod if args[3].endswith('-build') else self.app_pod]})
            self.fail('Unexpected CLI call: ' + repr(args))
        def response(url, **kwargs):
            return io.BytesIO(('{"status":"ok"}' if url.endswith('/healthz') else '<h1>Fortune Cookie 🥠</h1>').encode('utf-8'))
        with patch.dict(os.environ, {'APP_NAME': 'fortune-cookie', 'E2E_NS': '', 'DEV_POD': '', 'EXPECT_UPDATED_APP': 'true'}), patch.object(module, 'resource', resource), patch.object(module, 'oc', oc), patch.object(module.urllib.request, 'urlopen', response), contextlib.redirect_stdout(io.StringIO()):
            module.developer()

    def test_healthy_delivery_passes_without_mutations(self):
        self.check()

    def test_old_success_does_not_hide_new_failed_build(self):
        self.runs.insert(0, {'metadata': {'creationTimestamp': '2026-10-25T12:00:00Z'}, 'status': {'conditions': [{'type': 'Succeeded', 'status': 'True'}]}})
        self.run['status']['conditions'][0]['status'] = 'False'
        with self.assertRaisesRegex(AssertionError, 'Latest Tekton'):
            self.check()

    def test_wrong_build_image_is_rejected(self):
        self.run['spec']['params'][0]['value'] = 'placeholder'
        with self.assertRaisesRegex(AssertionError, 'matches the deployed image'):
            self.check()

    def test_non_restricted_application_is_rejected(self):
        self.app_pod['metadata']['annotations']['openshift.io/scc'] = 'privileged'
        with self.assertRaisesRegex(AssertionError, 'restricted-v2'):
            self.check()

    def test_privileged_build_is_rejected(self):
        self.build_pod['spec']['containers'][0]['securityContext']['privileged'] = True
        with self.assertRaisesRegex(AssertionError, 'No privileged build'):
            self.check()

    def test_host_user_namespace_build_is_rejected(self):
        self.build_pod['spec']['hostUsers'] = True
        with self.assertRaisesRegex(AssertionError, 'Linux user namespaces'):
            self.check()
