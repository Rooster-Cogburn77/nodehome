# Quantization Basics

## What It Is
Quantization reduces the precision of model weights from their training format (typically FP16/BF16, 16 bits per weight) to lower bit depths (Q8 = 8 bits, Q6 = 6 bits, Q4 = 4 bits). This shrinks the model's memory footprint proportionally.

## Why It Matters
A 70B parameter model at FP16 needs ~140GB of VRAM. The Sovereign Node has 72GB across 3x 3090s. Quantization makes large models fit:

| Precision | Bits/Weight | 70B Model Size | Fits in 72GB? |
|-----------|-------------|----------------|---------------|
| FP16 | 16 | ~140GB | No |
| Q8 | 8 | ~70GB | Barely |
| Q6 | 6 | ~52GB | Yes, with headroom |
| Q4 | 4 | ~35GB | Yes, lots of headroom |

## Quality vs Size Tradeoff
- **Q8:** Near-lossless. Virtually indistinguishable from FP16 on benchmarks.
- **Q6:** Slight quality loss on complex reasoning. Good balance for most use cases.
- **Q4:** Noticeable quality degradation on nuanced tasks. Fine for simpler workloads.
- **Below Q4:** Significant quality loss. Not recommended for serious use.

## Sovereign Node Target
Q6-Q8 for 70B models. This provides competitive intelligence quality while fitting within 72GB VRAM with room for KV cache (the memory needed for context window).

## Realistic Context Windows
At Q6-Q8 quantization, the KV cache for long context windows eats into available VRAM:
- 16K context: Comfortably fits alongside Q6 70B model
- 32K context: Tight but workable
- 128K context: NOT realistic at high quantization on 72GB - despite what some marketing claims suggest

## Tools
- **GGUF format:** Standard for quantized models (used by llama.cpp, Ollama)
- **GPTQ/AWQ:** Alternative quantization methods with different tradeoffs
- **ExLlama/ExLlamaV2:** Optimized inference engines for quantized models
