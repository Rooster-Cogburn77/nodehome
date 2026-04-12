# Software Stack (Planned)

**Status:** Not yet implemented. Hardware build in progress.

## OS
- **Ubuntu Server 24.04 LTS**
- Headless operation, SSH access
- NVIDIA driver + CUDA toolkit

## Model Serving
| Tool | Purpose | Notes |
|------|---------|-------|
| **Ollama** | First inference path and convenience serving | Easy model downloads, API compatible, good for smoke tests and small/single-GPU models; layer-split experiments are allowed but not the serious TP path |
| **vLLM** | Primary multi-GPU serving experiment path | Validate `TENSOR_PARALLEL_SIZE=3`; test CPU KV cache offload with 128GB RAM |
| **llama.cpp** | Direct GGUF benchmark/watch path | Track CUDA, quantization, tensor, and split-mode changes; do not make experimental tensor/split-mode a day-one dependency |
| **ExLlamaV2** | Optimized quantized inference | Best performance for GPTQ/EXL2 models |

Day-one serving posture:

- Start with Ollama to get working local inference quickly.
- Move to vLLM after baseline inference is stable and treat TP=3 as a benchmark/validation item, not a solved assumption.
- Test vLLM CPU KV cache offload because the node has 128GB RAM and only 72GB total VRAM.
- Before relying on Gemma4 in Ollama, run a flash-attention compatibility gate on RTX 3090/Ampere. If it fails, test with `OLLAMA_FLASH_ATTENTION=0`.
- Keep direct llama.cpp tensor/split-mode in the watch/benchmark lane while upstream marks it experimental.

## Agent / Orchestration
| Tool | Purpose | Notes |
|------|---------|-------|
| **Claw-code** | Claude Code agent harness (open-source) | github.com/instructkr/claw-code |
| **Open WebUI** | Chat interface | Browser-based, multi-model |

Working architectural framing:

- `Connectors` for actual service/system access
- `Manuals` (skills / repo-local guidance) for gotchas, workflow rules, and learned operating knowledge

This is a useful way to think about MCP vs skills in the Sovereign Node stack: not either/or, but connector layer plus knowledge layer.

## Knowledge Management
| Tool | Purpose | Notes |
|------|---------|-------|
| **Obsidian** | Knowledge base viewer/editor | Karpathy workflow: raw/ → wiki/ compilation |
| **Obsidian Web Clipper** | Article → markdown conversion | Feed into raw/ directory |

## Research Tools
| Tool | Purpose | Notes |
|------|---------|-------|
| **AutoResearch** | Autonomous ML experiments | Karpathy's repo, single-GPU experiments |
| **Nanochat** | LLM training pipeline | Full pipeline: tokenize → pretrain → finetune → serve |

| **Daily research sweeps** | Watch key feeds, repos, and blogs | Proposed: generate digests and promote only top items into `raw/` |
| **LLM weekly synthesis** | Future local rollup generation | Once Ollama is online, use local inference to synthesize weekly sweep rollups from daily digests |

Key public builders to watch in this stack: Georgi Gerganov / `llama.cpp`, Tim J. Baek / Open WebUI, and the LM Studio team.

Current W15 stack signals:

- `llama.cpp` split-mode/tensor work is active but still experimental, so it informs benchmarks rather than the day-one install plan.
- `vLLM` CPU KV cache offload is worth testing against the 3x RTX 3090 + 128GB RAM topology.
- Ollama remains the target first-run serving layer; Gemma4 needs an FA compatibility gate before being treated as stable on the node.
- Cheap 10GbE switching is bookmarked for future multi-node expansion, not a day-one purchase.

## Target Models (Day 1)

### Primary (Across 3 GPUs)
| Model | Size | Quantization | VRAM | Use Case |
|-------|------|-------------|------|----------|
| Llama 3.x 70B | 70B | Q6 | ~52GB (3 GPUs) | General intelligence, complex reasoning |
| DeepSeek-V3 | 70B+ | Q6-Q8 | ~52-70GB (3 GPUs) | Code, math, reasoning |

### Cognitive Core (Single GPU)
| Model | Size | VRAM | Use Case |
|-------|------|------|----------|
| Gemma 4 26B MoE | 3.8B active | <12GB (1 GPU) | Fast responses, always-on agent |

### Swarm Architecture
- GPU 0: Cognitive core (Gemma 4 26B, always running)
- GPU 1-2: Large model (70B) for complex tasks, loaded on demand
- OR: 3 independent small models for parallel agent swarm
