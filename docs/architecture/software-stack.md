# Software Stack (Planned)

**Status:** Not yet implemented. Hardware build in progress.

## OS
- **Ubuntu Server 22.04/24.04 LTS** (likely) or similar Linux
- Headless operation, SSH access
- NVIDIA driver + CUDA toolkit

## Model Serving
| Tool | Purpose | Notes |
|------|---------|-------|
| **Ollama** | Simple model management & serving | Easy model downloads, API compatible |
| **vLLM** | High-performance inference server | Better throughput for production use |
| **llama.cpp** | Direct GGUF inference | Low-level, maximum control |
| **ExLlamaV2** | Optimized quantized inference | Best performance for GPTQ/EXL2 models |

## Agent / Orchestration
| Tool | Purpose | Notes |
|------|---------|-------|
| **Claw-code** | Claude Code agent harness (open-source) | github.com/instructkr/claw-code |
| **Open WebUI** | Chat interface | Browser-based, multi-model |

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
