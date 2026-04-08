# Decision: TLC SSD Over QLC

**Date:** 2026-04
**Status:** Final

## Decision
Acer Predator GM7 2TB (TLC) at $269 instead of cheaper QLC alternatives at $130-150.

## Rationale
AI server workloads involve heavy sequential reads when loading models from disk to RAM to VRAM. QLC NAND has significantly worse write endurance and sustained read performance under load. The $120-140 premium for TLC is insurance against premature SSD failure.

## What Was Rejected
- $130-150 QLC drives: Adequate for consumer use but fail under sustained AI server read patterns
- $350 Acer Predator GM7000 (Amazon): Same quality tier but $80 more than the GM7 on eBay
