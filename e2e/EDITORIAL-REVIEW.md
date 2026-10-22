# Workshop editorial and coherence review — 22 October 2026

Reviewed all 11 participant pages, navigation, the facilitator README, diagrams and their generator, relevant deployment manifests, and both application-template branches.

## Corrections

- Kept Qwen3.8/MaaS on one L40S and the Fortune Cookie application; clarified that runtime app requests do not call the coding model.
- Distinguished internal inference from source delivery through an external ephemeral Git service.
- Added explicit workspace oc login, model readiness, complete shipping prompts and an Argo CD check for the pushed Git revision. Aligned the main template runbook with those prerequisites.
- Replaced the per-token cloud-bill claim: MaaS limits consumption, while a provisioned GPU still incurs infrastructure costs when idle. Power telemetry is not an electricity invoice. Removed misleading fixed cost/token extrapolations.
- Added facilitator-only scoped model/cache and GPU-pool cleanup, preserving the base cluster and shared operators. Kept On-Demand as the default and the documented Spot sandbox restriction.

- Aligned lab titles, navigation, persona transitions, terminal locations, timing and background readiness gates. Renamed “Prompt to Production” to “Prompt to Deployment” to match the demo outcome.
- Replaced automatic-compliance promises with agent-assisted review and direct cluster checks. The audit now reports scaffold differences instead of contradicting the template’s no-rewrite rule. Clarified the difference between the declared Deployment and the SCC-admitted Pod.
- Made the one-cluster-per-participant assumption explicit. Shared clusters need facilitator-managed app isolation and shared-resource cleanup.
- Fixed AsciiDoc shell-variable rendering and a missing generated-site favicon where applicable. Simplified the conclusions and template documentation.

## Verification

- Antora 3.1 build completed with no warnings or errors.
- All 11 pages appear in navigation; 288 generated local link/asset references resolve, including checked target fragments.
- All 44 shell source blocks pass `bash -n` (syntax only; no provisioning or cleanup commands executed).
- The documented OpenCode JSON matches the deployed platform ConfigMap.
- Chromium opened all participant pages with no missing article images; overview diagrams fit their content at desktop (1440 px) and mobile (390 px) widths. Browser launched with `--use-mock-keychain`.
- External reference checks covered 18 distinct linked URLs across both guides. Red Hat documentation rejects some automated HEAD requests; those references were checked through documentation/search retrieval. Azure Retail Prices requires GET. No confirmed dead reference remained.

This is an editorial/static/browser review, not a new full cloud E2E run. Existing runtime validation reports remain separate evidence. No cluster or deployment resources were changed during this review; the ARO app’s SCC was inspected read-only. The deferred OpenCode workshop companion experiment remains outside the participant path.
