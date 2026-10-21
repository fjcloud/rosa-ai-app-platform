# E2E Workshop Validation

Maps to workshop Act 1 (labs 1.1–1.4) and Act 2 (labs 2.1–2.3). Neither needs the Dev Spaces UI.

| Script | Persona | What it checks |
|--------|---------|----------------|
| `e2e/platform-run.sh` | Platform Engineer | GPU pool, operators, DSC (KServe + MaaS + dashboard + OGX), Dev Spaces, `LLMInferenceService/qwen3`, MaaS CRs, minted `sk-oai-` key, smoke `POST /chat/completions` |
| `e2e/dev-run.sh` | Developer | Template repo, OpenCode-generated Fortune Cookie, Tekton image, Argo CD sync, live route |

Cleanup: `e2e/platform-cleanup.sh` and `e2e/dev-cleanup.sh`.

## Prerequisites

- `oc` logged in with cluster-admin
- Workshop GitOps already applied (`deploy/operators`, `deploy/instances`, `deploy/inference`)
- `LLMInferenceService/qwen3` Ready in `llm-serving` and published through Models-as-a-Service

## Usage

```bash
export GIT_SERVER=https://gitpop.apps.sno.msl.cloud
bash e2e/platform-run.sh
bash e2e/dev-run.sh
```

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GIT_SERVER` | `https://gitpop.apps.sno.msl.cloud` | Git server base URL |
| `APP_NAME` | `fortune-cookie` | Name of the generated app (`dev-run.sh`) |
| `E2E_NS` | `workshop-e2e` | Namespace for the developer simulation pod |
| `LLM_NS` | `llm-serving` | Model namespace (`platform-run.sh`) |
| `MAAS_HOST` | `maas.<apps-domain>` | MaaS gateway hostname |

The scripts exit 0 if all checks pass, 1 if any fail. Each check prints ✅ or ⚠️ FAIL.

## GPU provisioning validation — 2026-10-21

The guide's creation command was accepted by ROSA CLI 1.2.53 on an existing ROSA HCP 4.19.49 cluster. Cluster/subnet discovery, the single replica, and the GPU taint were checked live. The alternate-zone subnet helper also passed creation and reuse checks; unused test subnets were removed.

AWS initially rejected `g6e.xlarge` launches in all four supported `us-east-1` zones with `InsufficientInstanceCapacity`. Attempts to reserve one `g6e.2xlarge` or `g6e.4xlarge` also failed in every zone. No reservation was created. Capacity later became available in `us-east-1d`: the on-demand `gpu` pool reached `1/1`, and its `g6e.xlarge` node passed the readiness helper with the expected GPU taint. GPU driver and model execution remain unverified; the full platform guide requires OpenShift 4.22 or later.

A Spot pool was then requested using the official ROSA 1.2.66 binary after verifying its release checksum. The regional G/VT Spot quota was sufficient, but the API rejected the request on 4.19.49 with `Spot Market Options are not allowed for this version`. No Spot pool or instance was created. The existing on-demand GPU worker remained Ready. ROSA 1.2.53 does not apply its creation Spot flag to HCP pools; verify the returned pool's `aws_node_pool.spot_market_options` with a current CLI instead of trusting flag acceptance.
