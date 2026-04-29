# Current State

**Last Updated:** 2026-04-27

## Active Work
- Parts are arriving and the next real move is staged assembly: inventory, bench POST, chassis install, then GPU bring-up.
- Sweep system is operational and now produces daily digests, weekly rollups, follow-up queue items, and assumption-pressure checks.
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

## Component Status
| Component | Price (incl tax) | Status |
|-----------|-----------------|--------|
| 3x RTX 3090 Gigabyte Turbo | $3,442 | Purchased, eBay #227287677142, FedEx air ETA Apr 16-28 |
| EPYC 7302P + H12SSL-i v2.0 | $985 | Arrived 2026-04-07 |
| PSU 1600W Titanium | $241 | Purchased |
| RAM 128GB DDR4-2133 ECC | $455 | Purchased, order #03-14469-02999, shipping from CA |
| SSD Acer GM7 2TB | $291 | Purchased |
| SilverStone RM400 chassis | ~$260 | Purchased, arriving Sat 2026-04-12 |
| Noctua NH-U9 TR4-SP3 cooler | $161 | Purchased from kuaka02 (Ada), shipping from China |
| Noctua NF-A12x25 PWM case fan | $0 | Have it (came with rack) |
| SysRacks 24x24 server rack | $75 | Purchased |

## Budget
- **Spent (incl tax):** ~$5,910
- **Over original $5,600 budget by:** ~$310 (cooler upgrade from Arctic $70 -> Noctua $161, plus rack)
- **All components purchased.** No remaining spend.

## Blocking Issues
- No purchasing blockers.
- No software version blocker. Current day-one targets are pinned Ollama `v0.21.2` and `vLLM v0.19.1`.

## Known Failures
None.
