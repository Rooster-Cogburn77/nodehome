# GPU Architecture Comparison

**Last Updated:** 2026-04-04

## Consumer vs Datacenter

| Spec | RTX 3090 | RTX 4090 | RTX 5090 | A100 | H100 |
|------|----------|----------|----------|------|------|
| VRAM | 24GB GDDR6X | 24GB GDDR6X | 32GB GDDR7 | 80GB HBM2e | 80GB HBM3 |
| FP32 | 35.6 TFLOPS | 82.6 TFLOPS | ~100+ TFLOPS | 19.5 TFLOPS | 51 TFLOPS |
| FP64 | 0.56 TFLOPS (1:64) | 1.29 TFLOPS (1:64) | ~1.5 TFLOPS | 9.7 TFLOPS (1:2) | 25.6 TFLOPS (1:2) |
| FP64 Ratio | **1:64 (crippled)** | **1:64 (crippled)** | **1:64 (crippled)** | **1:2 (full)** | **1:2 (full)** |
| Memory BW | 936 GB/s | 1,008 GB/s | ~1,700 GB/s | 2,039 GB/s | 3,350 GB/s |
| TDP | 350W | 450W | 575W | 300W | 700W |
| Price (2026) | $1,000-1,200 used | $1,800-2,200 used | $1,999 MSRP ($3,500 scalped) | TBD | TBD |

## Key Takeaways

### For LLM Inference (Our Use Case)
- RTX 3090 is the sweet spot: 24GB VRAM at $1,000 used
- 3x 3090 = 72GB VRAM for ~$3,200
- Memory bandwidth (936 GB/s per card) is the real performance driver for token generation
- FP64 doesn't matter for inference

### For CFD / Scientific Computing
- RTX cards are useless for FP64 workloads (1:64 ratio)
- A100/H100 have 1:2 FP64 ratio - literally 32x better per TFLOP
- Future upgrade path: swap 3090s for A100s when prices drop on used market

### For Training
- RTX 5090 with 32GB GDDR7 is interesting for small model training
- Serious training needs multi-GPU with NVLink (not available on consumer)
- A100/H100 have NVLink for multi-GPU scaling

## Upgrade Path for Sovereign Node
1. **Now:** 3x RTX 3090 (72GB, LLM inference)
2. **Future:** Swap to A100 40GB/80GB when ITAD prices drop (same PCIe slots, EPYC platform supports it)
3. **Far future:** Platform replacement for PCIe 5.0 + DDR5 if needed
