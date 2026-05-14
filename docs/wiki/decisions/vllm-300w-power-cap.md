# Decision: 300W + Top Fan for Sustained 2-GPU vLLM

**Date:** 2026-05-14
**Status:** Adopted for 2-GPU operation; persistent boot-time enforcement not yet installed
**Type:** authored

## Decision

For sustained 2-GPU vLLM serving on `homelab`, run with:

- Top fan on
- GPU 0 power limit: `300 W`
- GPU 1 power limit: `300 W`
- GPU 2 unused until the proper SF-1600F14HT PCIe cable arrives

Do not describe the GPU 2 pigtail as load-validated. GPU 2 remained idle during these tests (`1 MiB`, `0% util`, `P8`) and was only thermally exposed to chassis heat.

## Evidence

The 2026-05-14 validation used `Qwen/Qwen2.5-32B-Instruct-AWQ` under vLLM TP=2 on GPUs 0 and 1.

| Config | Result |
|--------|--------|
| `350 W`, no top fan | 180/180 soak passed; GPU0 final plateau `83-84 C` / `90% fan`; GPU1 `76-77 C`; GPU2 idle around `56 C` |
| `350 W + top fan` | 180/180 soak passed; GPU0 `77 C` / `82% fan`; GPU1 `71 C` / `72% fan`; GPU2 idle around `52 C`; request timing averaged `~4.96 s` |
| `300 W + top fan` | 180/180 soak passed; GPU0 `76 C` / `78% fan` / `299 W`; GPU1 `70 C` / `69% fan` / `290 W`; GPU2 `52 C`, `1 MiB`, `0% util`, `P8`; request timing averaged `~5.16 s` |

Post-`300 W` cooldown after about 6 minutes returned GPU0/GPU1/GPU2 to `45 C` / `40 C` / `41 C`. `./scripts/healthcheck.sh` returned `[HEALTHY] no failures, no warnings`.

## Rationale

The `300 W + top fan` profile keeps the same successful 2-GPU serving path while cutting the GPU power limit by about 14% per loaded card. The measured wall-clock cost on the sample request was about 4%, which is a favorable trade for a living-room rack where heat and fan noise matter.

The top fan remains mandatory for sustained 2-GPU work because it produced a direct measured improvement versus no-top-fan stock operation.

## Follow-Ups

- Install a narrow systemd unit only if persistent boot-time power caps are desired. See `docs/runbooks/nvidia-power-cap.md`.
- Do not include GPU 2 in any power-cap or sustained workload profile until the temporary pigtail rule is retired.
- Re-test thermals after the proper GPU 2 cable is installed and before adopting any 3-GPU TP=3 profile.
