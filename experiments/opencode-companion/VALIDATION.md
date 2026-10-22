# Live validation — 2026-10-22

Tested on the existing ROSA HCP 4.22.18 lab (`rosa-lxd8l`), in its actual Dev
Space, using **OpenCode 2.1.2** and the deployed **Qwen3.8** MaaS endpoint.

| Check | Result |
|-------|--------|
| Binary | Official `@opencode/cli-linux-x64@2.1.2` package verified against its npm SHA-512 integrity. |
| Configuration | Native V2 provider configuration, `companion` primary agent and `rosa-companion` skill loaded successfully. |
| First contact | Native interactive experience question rendered; French conversation followed the learner's language. |
| Wrong answer | Choosing A in the GPU quiz produced a hint and kept the saved step at 1. |
| Correct answer | Choosing B passed the GPU quiz and waited at the pacing question. |
| Explain more | Produced another explanation and returned to the same pacing choice. |
| Pause | Ended the turn with no pending form and preserved the checkpoint. |
| Resume | A new OpenCode conversation resumed at the saved pacing choice rather than restarting the quiz. |
| Six checkpoints | GPU/taint, OpenShift AI/Dev Spaces readiness, MaaS discovery and real inference, running workspace, successful builds/Synced Healthy app, GPU/token metrics all verified. |
| Completion | All six quizzes passed; each transition followed an explicit Next step choice; Finish workshop produced a recap. |
| Browser | Actual OpenCode 2 TUI and its native question visible in the Dev Spaces browser terminal. Chromium used `--use-mock-keychain`. |
| Unit checks | Seven tests passed: evidence gate, quiz gate, wrong answer, explicit next/resume, failed recheck, unexpected-error redaction, durable completion. |
| Isolation | Existing injected OpenCode remains 1.18.14; the experiment binary reports `opencode v2.1.2`. User progress was left fresh; automated course progress used a separate file. |

The live test drove real native question forms through the OpenCode 2 API. Quiz
answers were submitted as learner inputs; cluster evidence came from commands
executed by the companion in the workspace. The browser check separately
verified the terminal UI, including the initial selectable question.

One live MaaS discovery call returned an empty list despite the model being
available for inference. The companion correctly stopped, explained the failed
checkpoint, and offered **Retry the check**. Retrying listed the model and
returned `COMPANION_OK` from a real completion, after which the course continued.
The cause of that intermittent discovery result is not resolved by this
prototype.

This was an exploration of the existing deployment, not a fresh installation or
a new application build. No GPU pools, operators, application source, delivery
pipelines or billing settings were changed. The stopped Dev Space was started
for the experiment. ARO and multi-participant use were not tested.
