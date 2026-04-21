# Current State

**Last Updated:** 2026-04-18

## Active Work
- Parts are arriving and the next real move is staged assembly: inventory, bench POST, chassis install, then GPU bring-up.
- Sweep system is operational and now produces daily digests, weekly rollups, follow-up queue items, and assumption-pressure checks.
- Ollama `v0.21.0` now materially pressures the current `v0.20.5` bootstrap target; hold `v0.20.5` until `v0.21.0` is reviewed for Gemma4 / Ampere / RTX 3090 implications.
- `vLLM v0.19.1` is now worth reviewing before first install, since the stack was already pinned to `v0.19.0`.
- Current serving posture remains: Ollama first, vLLM second, direct `llama.cpp` benchmark/watch only.
- `Qwen3.6-35B-A3B` is now logged as a future vLLM benchmark candidate, not a day-one model target.
- `Kimi K2.6` is now logged as a serious future model-eval candidate, but it is not practical on the current 3x3090 node and is not part of the day-one local stack.

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
- Install-target review remains open: decide whether Ollama should stay pinned to `v0.20.5` or move to `v0.21.0`, and whether vLLM should stay at `v0.19.0` or bump to `v0.19.1`, after release-note review.

## Known Failures
None.
