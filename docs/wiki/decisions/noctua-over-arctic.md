# Decision: Noctua NH-U9 TR4-SP3 Over Arctic Freezer 4U-M

**Date:** 2026-04-07
**Type:** authored
**Status:** Final

## Decision
Switched CPU cooler from Arctic Freezer 4U-M ($65) to Noctua NH-U9 TR4-SP3 ($161 incl tax).

## Why
The Arctic Freezer 4U-M is 145mm tall. The SilverStone RM400 allows 148mm without the card retainer bracket. That's 3mm clearance — within manufacturing tolerance. No real-world confirmation of this combo exists online.

The Noctua NH-U9 TR4-SP3 is 125mm tall, giving 23mm clearance without bracket or 5mm with bracket. This also means the card retainer bracket can likely stay, which helps support 3x heavy RTX 3090s.

## Why Not Supermicro SNK-P0064AP4?
The Supermicro ($84 incl tax) was the budget pick at 126mm / 22mm clearance. But it runs at 38 dBA — louder than 3x idle blower 3090s (33-35 dBA). Since the server lives in the living room, the CPU cooler becomes the loudest component at idle. The Noctua at 23 dBA is near-silent.

## Alternatives Considered
| Cooler | Height | Clearance | Noise | Price (incl tax) | Verdict |
|--------|--------|-----------|-------|-----------------|---------|
| Arctic Freezer 4U-M | 145mm | 3mm | 26 dBA | ~$65 | Too tight, risky |
| Noctua NH-U9 TR4-SP3 | 125mm | 23mm | 23 dBA | $161 | Chosen |
| Supermicro SNK-P0064AP4 | 126mm | 22mm | 38 dBA | ~$84 | Too loud at idle |
| Dynatron A50 | 110mm | 38mm | 64 dBA | ~$45 | Jet engine at full speed |

## Cost Impact
+$91 over original Arctic spec. Total build now ~$5,910 vs $5,600 budget. Accepted trade-off for silence at idle and elimination of clearance risk.
