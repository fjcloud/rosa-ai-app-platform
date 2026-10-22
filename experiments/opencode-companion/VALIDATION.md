# Validation — Cloud Terminal / RHDP bastion

The current experiment is the **whole workshop companion on the bastion**.
The earlier six-checkpoint Dev Spaces-only prototype did not match the intended
entry point and has been replaced.

Environment: existing ROSA HCP 4.22.18 lab (`rosa-lxd8l`), OpenCode 2.1.2 on
`bastion.lxd8l`, and the already deployed Qwen3.8 MaaS endpoint.

## Checks

- **Cloud Terminal browser check passed:** opened the published launcher,
  retrieved the assignment through the normal workshop-ID flow, typed
  `workshop` in its real WeTTY iframe, and verified OpenCode 2's selectable
  learner question inside that terminal. The final Mini view hides raw shell
  output while retaining explanations and interactive questions. Chromium used
  `--use-mock-keychain`.

- The full native OpenCode 2 dialogue passed all ten checkpoints on the bastion:
  Act 0, GPU, operators, serving, developer handoff, workspace, delivery, audit,
  metrics and conclusion. Every checkpoint had a successful live check, a quiz
  and an explicit learner choice before advancement.
- A deliberately wrong Act 0 answer produced a hint and stayed on Act 0.
  Pause preserved it; a new conversation resumed the saved pacing choice.
- The Dev Space was idle-stopped. The companion blocked at Lab 2.1 until that
  existing workspace was restarted, then continued. The companion itself
  remained on the bastion throughout.

- Verified the official pinned Linux x64 binary's SHA-512 integrity.
- Installed `workshop` in the bastion login PATH. It starts at Act 0, not in a
  developer workspace. The model key is loaded from the existing Secret into
  process memory; no key or new login was requested.
- Fixed an actual bastion issue: private OpenCode XDG directories hid ROSA's
  existing OCM login. Cluster commands now retain the host's configuration paths.
  Verified normal ROSA login and successful onboarding without reauthentication.
- Eleven unit tests passed, including wrong answers, explicit progression,
  durable completion, existing-resource reuse, unsupported manual actions,
  stopping on a failed apply, and preserving host authentication locations.

The lab is already deployed. Inspecting its resources exercises the teaching
and verification path; it does not constitute a fresh install. Platform action
failure/no-op behavior is unit tested; no platform reinstallation, billing
change, new GPU pool, or application rebuild was performed.

Bootstrap remains a limitation for a new workshop: the companion needs a model
before Lab 1.3. This test reuses the existing lab's model. ARO and multi-user
operation have not been tested.
