# Current State

**Last Updated:** 2026-05-01

## Active Work
- Hardware bring-up has progressed past inspection into a safe bench-power checkpoint: PSU/cable inventory was completed, the motherboard/CPU/RAM/cooler were powered on safely, and no immediate electrical fault was observed.
- Repo-truth hardware limit: the latest durable repo evidence does **not** prove current in-chassis wiring state, current BMC/KVM state, or a successful host POST. The latest proved blocker remains host power / POST verification.
- Hardware safety rule for this project is now explicit: no intentional pin shorting, no guessed header operations, and no undocumented power-control steps during bring-up. Only labeled connectors, documented headers, or approved vendor tools/adapters are allowed.
- This is the first full server build in this configuration. It is expected that some parts may not fit perfectly on the first attempt and that an extra cable, bracket, adapter, or replacement part may still be needed to finish cleanly.
- Sweep system is operational and now produces daily digests, weekly rollups, follow-up queue items, and assumption-pressure checks.
- Sweep workflow now also produces a generated daily operator brief (`docs/sweeps/operator/`) so triage does not require pasting digests into chat.
- The operator brief now has basic scaling guards: recommendation line, source/entity caps, and suppression of already-triaged rows.
- The sweep scheduler was repaired on 2026-04-27 after laptop-style task settings caused missed runs and `0x800710E0` refusals; tasks now have a real working directory and `StartWhenAvailable=true`.
- X/OpenRSS source health was also recovered on 2026-04-27 by auto-enabling OpenRSS fallback when no `X_BEARER_TOKEN` exists and clearing stale X-only quarantine state.
- Release-note review remains resolved in favor of `Ollama v0.21.2` for day-one install, and the bootstrap now pins that version explicitly instead of following latest stable.
- `vLLM` is now deliberately pinned to `v0.19.1` instead of `v0.19.0`.
- `Ollama 0.22.0` / `0.22.1-rc0` now pressure the target again, but current evidence says they are mostly new-model / MLX / launch changes rather than Linux RTX 3090 must-haves, so the pin stays at `0.21.2` for now.
- Current serving posture remains: Ollama first, vLLM second, direct `llama.cpp` benchmark/watch only.
- `Qwen3.6-35B-A3B` is now logged as a future vLLM benchmark candidate, not a day-one model target.
- `Qwen3.6-Max-Preview` is now logged as a hosted proprietary coding model to watch for future routing/escalation, not a local-node target.
- `Kimi K2.6` is now logged as a serious future model-eval candidate, but it is not practical on the current 3x3090 node and is not part of the day-one local stack.
- `llm-openrouter 0.6` is now logged as future routing/fallback tooling to watch, not part of the day-one local stack.
- Sakana's `Conductor` paper is now logged as a real future orchestration signal for Nodehome: relevant to a later "manager of models" workflow layer, but not to the immediate hardware build.
- Cloudflare's new agent provisioning flow is now logged as a real future "agent-operated infrastructure" signal for Nodehome: relevant to a later orchestration/product layer, but not to the immediate hardware build.
- SubQ is now logged as a hosted long-context architecture watch item. Early access was requested on 2026-05-05; status is pending review/waitlist.
- Railway changelog #0288 is now logged as a practical agent-guardrails signal: reversible destructive actions, safer shared machine identity, and explicit deployment controls matter more as agents become operators.
- `llama.cpp` `b9010` is now logged as a real multi-GPU CUDA watch item for this box: it fixes PCI bus ID de-dupe behavior that could ignore other GPUs or trigger OOM conditions.
- `Ollama v0.23.0` has now been reviewed at a high level and does not currently justify moving the pinned `v0.21.2` day-one target for the Linux 3x3090 stack.
- The May 4-5 sweeps did not materially change the stack posture. Recent `llama.cpp` CUDA / multi-GPU fixes remain watch items, but no new release signal justified moving pins or changing the serving order.
- The 2026-05-05 extended sweep should be treated as lower-confidence evidence due to heavy X/OpenRSS degradation (`21` social feed failures, including `19` timeouts).

## Component Status
| Component | Price (incl tax) | Status |
|-----------|-----------------|--------|
| 3x RTX 3090 Gigabyte Turbo | $3,442 | Purchased, eBay #227287677142 |
| EPYC 7302P + H12SSL-i v2.0 | $985 | Arrived 2026-04-07 |
| PSU 1600W Titanium | $241 | Purchased |
| RAM 128GB DDR4-2133 ECC | $455 | Purchased, order #03-14469-02999 |
| SSD Acer GM7 2TB | $291 | Purchased |
| SilverStone RM400 chassis | ~$260 | Purchased |
| Noctua NH-U9 TR4-SP3 cooler | $161 | Purchased from kuaka02 (Ada) |
| Noctua NF-A12x25 PWM case fan | $0 | Have it (came with rack) |
| SysRacks 24x24 server rack | $75 | Purchased |

## Budget
- **Spent (incl tax):** ~$5,910
- **Over original $5,600 budget by:** ~$310 (cooler upgrade from Arctic $70 -> Noctua $161, plus rack)
- **All components purchased.** No remaining spend.

## Blocking Issues
- No purchasing blockers.
- No software version blocker. Current day-one targets are pinned Ollama `v0.21.2` and `vLLM v0.19.1`.
- Host POST is still not proved. The repo-safe next step remains: positively identify the documented host power-control path and verify BMC/LAN behavior before improvising anything at the front-panel header.
- Reminder: fitment surprises or a late extra order would be normal for a first-time dense rack/GPU build and should be treated as part of the learning process, not as a project failure.

## Known Failures
None.
