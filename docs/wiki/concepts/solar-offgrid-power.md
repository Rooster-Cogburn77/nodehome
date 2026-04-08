# Solar / Off-Grid Power Reality Check

**Last Updated:** 2026-04-04

## The Claim (Original Doc)
The Sovereign Node could run on solar/Jackery portable power, enabling off-grid AI operation.

## The Math
- Full load power draw: ~1,255W (3x 350W GPUs + 155W CPU + misc)
- Jackery Explorer 2000 Plus: 2,042Wh capacity
- Runtime at full load: **~1.6 hours**
- Runtime at idle/light inference: ~4-6 hours

## Reality
Solar/battery is supplemental only. Useful for:
- Brief power outage bridging
- Light inference tasks on a single GPU
- Demonstrating portability as a concept

NOT viable for:
- Sustained multi-GPU inference
- Training workloads
- 24/7 operation

## Corrected Framing
The original executive summary implied solar could meaningfully power the rig. The corrected version positions solar as "supplemental/emergency" with wall power as the primary source. A 1,600W titanium PSU drawing from a standard US 20A circuit (2,400W capacity) is the real power plan.
