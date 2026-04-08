# Decision: RAM Speed Irrelevant for This Build

**Date:** 2026-04-04
**Status:** Final

## Decision
Purchased DDR4-2133 instead of DDR4-2666/2933/3200. Saved $280-580.

## Rationale
LLM inference is GPU-memory-bandwidth-bound, not system-RAM-bandwidth-bound. Once models are loaded from disk → RAM → VRAM, system RAM speed is out of the picture. The only visible difference is model load time at startup (seconds, not minutes).

## Price Comparison (April 2026)
| Speed | 128GB Kit Price | Savings vs 2933 |
|-------|----------------|-----------------|
| DDR4-2133 | $420 (purchased) | $280-580 |
| DDR4-2400 | $549 | $151-451 |
| DDR4-2933 | $700-1,000+ | baseline |
| DDR4-3200 | $800-1,200+ | negative |

## Where RAM Speed WOULD Matter
- CPU-based preprocessing of large datasets
- CPU-based fine-tuning/training (not our primary use case)
- If models spill from VRAM to system RAM (avoid this regardless)

## What Gemini Got Wrong
Gemini claimed DDR4-2933 128GB kits available at $300-330. Actual market is $700-1,000+. Specific sellers cited (cloud_storage_corp, serverpartdeals) exist but don't have listings at those prices.
