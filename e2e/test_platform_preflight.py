"""Exercise preflight failures without a cloud account or cluster.

Run: python3 -m unittest discover -s e2e -p 'test_platform_preflight.py'
"""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
FAKE_OC = r'''#!/usr/bin/env python3
import json,os,sys
args=[a for a in sys.argv[1:] if not a.startswith('--request-timeout=')]
with open(os.environ['CALL_LOG'],'a') as f: f.write(json.dumps(args)+'\n')
if args[:2]==['get','clusterversion']:
    print(os.environ['CLUSTER_VERSION_JSON'])
elif args==['whoami']:
    print('workshop-admin')
elif args[:2]==['auth','can-i']:
    print('yes')
elif args[:2]==['get','nodes']:
    sys.exit('CPU check must not precede the version check')
elif args[0]=='get' and args[1].startswith('deployment/'):
    if os.environ.get('OPERATOR_MODE')=='missing': sys.exit(1)
    print(args[1])
elif args[0]=='wait':
    if os.environ.get('OPERATOR_MODE')=='unavailable': sys.exit('Deployment never became Available')
    print(args[1]+' condition met')
elif args[:2]==['get','subscriptions']:
    print('operator subscription pending')
else:
    sys.exit('Unexpected oc operation: '+repr(args))
'''


class PlatformPreflight(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.log = self.directory / 'calls.jsonl'
        executable = self.directory / 'oc'
        executable.write_text(FAKE_OC)
        executable.chmod(0o755)
        for name in ('aws', 'rosa', 'git', 'jq', 'curl'):
            executable = self.directory / name
            executable.write_text('#!/bin/sh\nexit 0\n')
            executable.chmod(0o755)
        self.env = dict(os.environ, PATH=str(self.directory)+os.pathsep+os.environ['PATH'],
                        CALL_LOG=str(self.log), OPERATOR_WAIT_SECONDS='1')
        self.version('4.22.18')

    def version(self, current, desired=None, progressing=False):
        self.env['CLUSTER_VERSION_JSON'] = json.dumps({'status': {
            'desired': {'version': desired or current},
            'history': [{'version': current, 'state': 'Completed'}],
            'conditions': [{'type': 'Progressing', 'status': 'True' if progressing else 'False'}],
        }})

    def run_script(self, name):
        return subprocess.run(['bash', str(ROOT/'scripts'/name)], env=self.env,
                              capture_output=True, text=True, timeout=15)

    def calls(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def test_old_cluster_stops_before_operator_wait(self):
        self.version('4.19.50')
        result = self.run_script('wait-for-platform.sh')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('4.19.50', result.stderr)
        self.assertIn('4.22 Gateway API', result.stderr)
        self.assertEqual(len(self.calls()), 1)

    def test_new_target_is_not_a_completed_upgrade(self):
        self.version('4.19.50', '4.22.18', progressing=True)
        self.assertNotEqual(self.run_script('check-version.sh').returncode, 0)

    def test_progressing_cluster_stops(self):
        self.version('4.22.18', progressing=True)
        result = self.run_script('check-version.sh')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('update in progress', result.stderr)

    def test_unknown_completed_version_stops(self):
        self.env['CLUSTER_VERSION_JSON'] = json.dumps({'status': {'desired': {'version': '4.22.18'}}})
        self.assertNotEqual(self.run_script('check-version.sh').returncode, 0)

    def test_ready_operators_are_checked_without_mutation(self):
        result = self.run_script('wait-for-platform.sh')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(sum(c[0]=='wait' for c in self.calls()), 9)
        self.assertTrue(all(c[0] in ('get', 'wait') for c in self.calls()))

    def test_missing_operator_times_out(self):
        self.env['OPERATOR_MODE'] = 'missing'
        result = self.run_script('wait-for-platform.sh')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('was not created within 1 seconds', result.stderr)
        self.assertFalse(any(c[0]=='wait' for c in self.calls()))

    def test_failed_availability_stops_remaining_checks(self):
        self.env['OPERATOR_MODE'] = 'unavailable'
        result = self.run_script('wait-for-platform.sh')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(sum(c[0]=='wait' for c in self.calls()), 1)

    def test_onboarding_reports_version_before_cpu_capacity(self):
        self.version('4.19.50')
        result = self.run_script('onboard.sh')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('4.19.50', result.stderr)
        self.assertFalse(any(c[:2]==['get', 'nodes'] for c in self.calls()))


if __name__ == '__main__':
    unittest.main()
