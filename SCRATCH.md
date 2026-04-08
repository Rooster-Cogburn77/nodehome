# Session Scratch - 2026-04-07
Focus: Finalizing Sovereign Node v1.0 BOM and Documentation Architecture.

## Decisions
- **SSD:** Acer Predator GM7 2TB ($269) locked. TLC mandatory for AI server loads.
- **PSU:** Super Flower 1600W Titanium Refurbished ($223) secured from ReSpec.io.
- **Cooler:** Noctua NH-U9 TR4-SP3 ($161.29) secured from Ada (kuaka02) to ensure silent idle and 4U height clearance.
- **GPUs:** 3x Gigabyte RTX 3090 Turbo Blowers ($3,442.35) secured from Ada (kuaka02). 2-slot blower design is the hard constraint for density.

## Current State
- **Secured (Ordered/Arrived):** Motherboard (H12SSL-i), CPU (EPYC 7302P), PSU (1600W Titanium), SSD (Acer GM7), GPUs (3x 3090 Blowers), RAM (128GB Samsung), Cooler (Noctua SP3), Chassis (RM400), Rack (SysRacks 24x24).
- **In Progress:** Awaiting remaining deliveries (GPUs ETA Apr 16-28).
- **Next:** Inspect EPYC socket and BIOS/BMC status. Plan breadboard test.

## Key Details
- **Supermicro H12SSL-i Rev 2.0:** Arrived. Verified Rev 2.0 status.
- **24x24 Rack:** 17.5" case depth (RM400) fits with ample rear clearance.
- **Software Path:** `claw-code` + local Ollama/vLLM backend.
