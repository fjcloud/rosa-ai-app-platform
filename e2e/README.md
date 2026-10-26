# ROSA workshop validation

Follow the participant guide in the assigned RHDP cluster, then run these checks from an authenticated bastion:

```sh
bash e2e/platform-run.sh
bash e2e/dev-run.sh
bash e2e/observability-run.sh
```

| Check | Evidence |
| --- | --- |
| Platform | GPU pool, operators, DSC, Dev Spaces, Qwen LLMInferenceService, MaaS catalog/key and a real completion |
| Developer | Latest Tekton build, matching image, Argo CD Synced/Healthy, HTTPS application, resources, probes and restricted security |
| Observability | DCGM/vLLM series, recorded tokens, dashboard and enforced MaaS quota |

Prepare the platform and build the application through the real Dev Spaces workshop first. The developer check creates no simulation pod, namespaces or permission grants. No teardown is performed; the environment remains available until RHDP expiration. The platform check makes a model smoke request.

## Check the real workspace too

```sh
E2E_NS=<devspaces-namespace> DEV_POD=<workspace-pod> DEV_CONTAINER=dev \
  bash e2e/dev-run.sh
```

This also verifies source files, local Go compilation and equality of the workspace, pushed and Argo CD Git revisions. Source is read from `PROJECT_SOURCE` in the workspace. `APP_NAME` defaults to `fortune-cookie`; `EXPECT_UPDATED_APP=true` checks the emoji update from Act 2.

## Local regression checks

```sh
make test
make docs
```

Tests cover version and worker-capacity preflight, bounded operator waits and scoped developer preparation. Use an already-completed OpenShift 4.22 or later cluster for live checks; preflight rejects older clusters and unfinished upgrades.

Earlier GPU-capacity/Spot trials and the retired administrator simulation remain in [the pre-cleanup revision](https://github.com/fjcloud/rosa-ai-app-platform/tree/c2cec6da6588e687c2fdfd2f6f81fca6a14f9563). The current path uses the scoped identity prepared in Lab 1.5.
