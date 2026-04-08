# Decision: EPYC 7302 Over Threadripper

**Date:** 2026-04
**Status:** Final

## Decision
AMD EPYC 7302 (16C/32T) on Supermicro H12SSL-i motherboard.

## Rationale
- **128 PCIe 4.0 lanes** - Each 3090 gets full x16 bandwidth, no bifurcation needed
- **ECC memory support** - Server-grade reliability for 24/7 operation
- **Single socket simplicity** - H12SSL-i is a well-documented server board
- **Cost:** $910 for CPU+mobo combo (tugm4470 eBay deal)

## Alternatives Considered
- **Threadripper:** Fewer PCIe lanes (64 on most models), more expensive, consumer-oriented
- **Threadripper PRO:** 128 lanes but much more expensive platform
- **Intel Xeon:** Comparable lane count but AMD has better perf/dollar in this generation
- **Cheaper EPYC (7002 series lower SKU):** Considered downgrading CPU to save ~$100, but the 7302 combo deal at $910 was cheaper than separate budget CPU + board

## Key Specs
- 16 cores / 32 threads @ 3.0GHz base / 3.3GHz boost
- 128 PCIe 4.0 lanes
- 8 DIMM slots (supports up to 2TB RAM)
- DDR4-3200 native support (running at 2133 per RAM decision)
