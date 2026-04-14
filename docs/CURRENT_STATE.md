# Current State

**Last Updated:** 2026-04-14

## Active Work
- Parts are arriving and the next real move is staged assembly: inventory, bench POST, chassis install, then GPU bring-up.
- Sweep system is operational and now produces daily digests, weekly rollups, follow-up queue items, and assumption-pressure checks.
- Ollama `v0.20.7` / `v0.20.8` now pressure the current `v0.20.5` bootstrap target; hold `v0.20.5` until the newer releases are reviewed for Gemma4 / Ampere / RTX 3090 implications.
- Current serving posture remains: Ollama first, vLLM second, direct `llama.cpp` benchmark/watch only.

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
- Install-target review remains open: decide whether Ollama should stay pinned to `v0.20.5` or move to a newer release after release-note review.

## Known Failures
None.
