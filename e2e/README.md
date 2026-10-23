# E2E Workshop Validation

Checks the platform, developer workflow, and Act 3 observability. The developer assertions also support an application built in a real Dev Space.

| Script | Persona | What it checks |
|--------|---------|----------------|
| `e2e/platform-run.sh` | Platform Engineer | GPU pool, operators, DSC (KServe + MaaS + dashboard + OGX), Dev Spaces, `LLMInferenceService/qwen3`, MaaS CRs, model discovery with the minted `sk-oai-` key, smoke `POST /chat/completions` |
| `e2e/dev-run.sh` | Developer | Template repo, OpenCode-generated Fortune Cookie, Tekton image, Argo CD sync, live route, resource/probe/security audit |
| `e2e/observability-run.sh` | Both | Live DCGM and vLLM metrics, recorded tokens, dashboard, active MaaS quota |

Cleanup: `e2e/platform-cleanup.sh` and `e2e/dev-cleanup.sh`.

## Prerequisites

- `oc` logged in with cluster-admin
- Workshop GitOps already applied (`deploy/operators`, `deploy/instances`, `deploy/inference`)
- `LLMInferenceService/qwen3` Ready in `llm-serving` and published through Models-as-a-Service

## Preflight regression checks

These checks use a stub OpenShift CLI and do not connect to a cloud account:

```bash
python3 -m unittest discover -s e2e -p 'test_platform_preflight.py'
```

They cover 4.19 rejection, incomplete upgrades, operator timeouts, stop-on-failure behavior and checking version before CPU capacity. `scripts/wait-for-platform.sh` uses a default 600-second budget for Deployment creation and then availability, per operator; `OPERATOR_WAIT_SECONDS` overrides that duration for tests.

## Usage

```bash
export GIT_SERVER=https://gitpop.apps.sno.msl.cloud
bash e2e/platform-run.sh
bash e2e/dev-run.sh
bash e2e/observability-run.sh
```

To validate the application already built in a real Dev Space, set its pod and container. The runner uses `~/fortune-cookie`; link it to the existing project directory once if needed. This mode leaves workspace identity, files, and pods in place.

```bash
VALIDATE_ONLY=true \
E2E_NS=<devspaces-namespace> DEV_POD=<workspace-pod> DEV_CONTAINER=dev \
  bash e2e/dev-run.sh
```

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GIT_SERVER` | `https://gitpop.apps.sno.msl.cloud` | Git server base URL |
| `APP_NAME` | `fortune-cookie` | Name of the generated app (`dev-run.sh`) |
| `E2E_NS` | `workshop-e2e` | Namespace for the developer simulation pod |
| `LLM_NS` | `llm-serving` | Model namespace (`platform-run.sh`) |
| `VALIDATE_ONLY` | `false` | Validate an existing application without creating a simulation pod |
| `EXPECT_UPDATED_APP` | `false` | Also check the fortune-cookie emoji after the ship-a-change exercise |
| `DEV_POD` | `e2e-developer` | Existing workspace pod for validation |
| `DEV_CONTAINER` | empty | Workspace container, usually `dev` |
| `MAAS_HOST` | `maas.<apps-domain>` | MaaS gateway hostname |

The scripts exit 0 if all checks pass, 1 if any fail. Each check prints ✅ or ⚠️ FAIL.

## GPU provisioning validation — 2026-10-21

The guide's creation command was accepted by ROSA CLI 1.2.53 on an existing ROSA HCP 4.19.49 cluster. Cluster/subnet discovery, the single replica, and the GPU taint were checked live. The alternate-zone subnet helper also passed creation and reuse checks; unused test subnets were removed.

AWS initially rejected `g6e.xlarge` launches in all four supported `us-east-1` zones with `InsufficientInstanceCapacity`. Attempts to reserve one `g6e.2xlarge` or `g6e.4xlarge` also failed in every zone. No reservation was created. Capacity later became available in `us-east-1d`: the on-demand `gpu` pool reached `1/1`, and its `g6e.xlarge` node passed the readiness helper with the expected GPU taint. GPU driver and model execution remain unverified; the full platform guide requires OpenShift 4.22 or later.

A Spot pool was then requested using the official ROSA 1.2.66 binary after verifying its release checksum. The regional G/VT Spot quota was sufficient, but the API rejected the request on 4.19.49 with `Spot Market Options are not allowed for this version`. No Spot pool or instance was created. The existing on-demand GPU worker remained Ready. ROSA 1.2.53 does not apply its creation Spot flag to HCP pools; verify the returned pool's `aws_node_pool.spot_market_options` with a current CLI instead of trusting flag acceptance.

## ROSA 4.22 validation — 2026-10-22

The hosted control plane was upgraded through the supported 4.20.42 and 4.21.37 releases to **4.22.18**. Both worker pools also reached 4.22.18: two `m6a.xlarge` CPU nodes and one On-Demand `g6e.xlarge` GPU node, all Ready on Kubernetes 1.35.8. All 23 cluster operators were available with none degraded. Temporary CPU capacity was removed and the original replacement settings restored (`max-surge=1`, `max-unavailable=0`).

The existing `scripts/onboard.sh` and `scripts/wait-for-gpu.sh` checks passed. The published Cloud Terminal launcher also passed its live browser test against the upgraded cluster, including catalog lookup, terminal embedding, and authenticated `oc` access.

The account was missing `AWSServiceRoleForEC2Spot`; the standard service-linked role was created and verified. A separate GPU Spot pool was then requested with ROSA CLI 1.2.66. On 4.22.18 the API accepted it and returned non-null Spot market options, but AWS denied the actual `ec2:RunInstances` request through an organization service control policy. No Spot worker was provisioned; the failed test pool was removed. The working On-Demand GPU remains the default for this RHDP account.

GPU driver installation, model serving, and the full platform/developer simulations were not run during this cluster upgrade.

One residual platform condition remains: `ClusterVersion.Upgradeable=False` with `ResourceDeletesInProgress` for deployment `openshift-kube-storage-version-migrator/migrator`. That deployment is running, with no deletion timestamp or finalizers. The 4.22.18 release is completed and all cluster operators remain available; another minor upgrade requires this managed cleanup condition to be resolved. No upgrade gate or running migrator deployment was forced or removed.

## Full live workshop — 2026-10-22

**Acts 0–3 passed on ROSA HCP 4.22.18 (`rosa-lxd8l`).** This run extends the earlier upgrade-only checks above.

The final footprint is **five `m6a.xlarge` CPU workers plus one On-Demand `g6e.xlarge` GPU worker**. All six nodes are Ready; all 23 cluster operators are available and none are degraded. The two original CPU workers could not schedule the complete platform, Dev Space, and personal Argo CD. Onboarding now checks for at least 17.5 allocatable CPU cores outside the GPU pool.

| Area | Live result |
|------|-------------|
| Launcher | Published GitHub Pages app retrieved the catalog assignment and embedded an authenticated WeTTY terminal. Browser checks use `--use-mock-keychain`. |
| GPU | NVIDIA L40S, driver 595.91.07, CUDA validator Succeeded, one allocatable GPU. |
| Platform | RHOAI 3.5.2, KServe, MaaS, dashboard, OGX, Dev Spaces 3.30.2, Pipelines 1.24.1 and GitOps 1.22.2 ready. Managed LeaderWorkerSet kept enabled. |
| Inference | Qwen3.8-27B-INT4 Ready; real completions with the injected key returned HTTP 200; an invalid key returned HTTP 401. Model discovery passed with both an OpenShift user token and the Dev Spaces API key. |
| Dev Spaces | Actual factory launch, repository trust, VS Code workspace trust, browser terminal, OpenCode 1.18.14 and injected configuration checked. |
| Developer | Real OpenCode plan/build session generated the Go app, pushed to a personal GitPop repository, built through Tekton, and deployed through the developer's Argo CD. |
| Iteration | Ship-a-change added ten fortunes; a third build corrected the cookie emoji. All three PipelineRuns Succeeded. The image digest changed and Argo CD finished Synced / Healthy at the pushed Git revision. |
| Audit | Resource limits, health probes, restricted pod security and HTTPS Route checked through OpenCode and against the live resources. |
| Browser | Fortune Cookie rendered the correct emoji; personal Argo CD login showed Synced / Healthy; OpenShift AI showed Qwen3.8 Ready, its active key and 5M tokens / 24h subscription; console metrics displayed GPU and token series. |
| Scripts | `platform-run.sh`, `dev-run.sh` against the real workspace (`VALIDATE_ONLY=true EXPECT_UPDATED_APP=true`), and `observability-run.sh` all exited 0. |

Corrections from this run:

- Install `workshop-git-clone` and `workshop-buildah` after Pipelines is ready. Keep workshop tasks separate from operator-owned tasks; the shared Go template references those names.
- Wait for Authorino resources before configuring TLS, allow cold Dev Spaces images more time, and provide CPU capacity instead of disabling managed operators or patching their UI deployments onto the GPU.
- Omit the optional `opendatahub.io/context-window` annotation on `MaaSModelRef`: MaaS serializes it as a string while the Gen AI catalog expects an integer, producing HTTP 502. Removing that metadata restored the catalog. The vLLM and OpenCode 262144-token limits remain configured.
- Use the current UI paths: **Gen AI studio → AI asset endpoints** and **Gen AI studio → API keys → Subscriptions**.

Limits: the Spot SCP restriction and the managed migrator upgrade condition described above remain. The workshop uses On-Demand. Playground/RAG are outside this run; no OGXServer was deployed, and the UI's background LlamaStack discovery requests return HTTP 500 without preventing the MaaS catalog from loading. No ARO cluster was available for a live run; shared manifest fixes do not constitute ARO validation.
