# Decision: Blower GPUs Mandatory

**Date:** 2026-04
**Status:** Final

## Decision
All GPUs must be 2-slot blower/turbo form factor. No open-air cards.

## Rationale
Slot physics: 3 open-air GPUs (2.7-3.5 slots each) physically cannot fit side by side in a 4U chassis. The SilverStone RM400 has 7 expansion slots. Three 3-slot cards = 9 slots. Doesn't fit.

Blower cards are exactly 2 slots each. 3 x 2 = 6 slots. Fits with room to spare.

Additionally, blower cards exhaust heat out the rear of the chassis. Open-air cards dump heat into the case, which in a dense 4U rack creates a thermal nightmare for neighboring cards.

## Alternatives Considered
- **Open-air cards:** $750+ cheaper but physically impossible with 3 GPUs
- **2 open-air + waterblock on third:** Overengineered, maintenance burden
- **2 GPUs instead of 3:** Loses 24GB VRAM, defeats purpose

## Compatible Blower Cards (Verified)
- Gigabyte RTX 3090 Turbo (GV-N3090TURBO-24GD)
- GALAX RTX 3090 Turbo
- MSI RTX 3090 Turbo / AERO S
- ASUS RTX 3090 Turbo
- Leadtek WinFast RTX 3090

## NOT Compatible (Verified)
- PNY RTX 3090 (all models are XLR8 open-air - no blower exists)
- Dell OEM RTX 3090 (dual-fan, not blower)
- NVIDIA Founders Edition (flow-through cooler, 2.5+ slots)
