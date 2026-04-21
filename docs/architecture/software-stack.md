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
| **Kimi K2.6 (future eval)** | Open-source frontier model to track for local/runtime evaluation and fallback economics | Officially supports `vLLM`, `SGLang`, and `KTransformers`; too large to treat as a practical 3x3090 day-one local target |
| **llm-openrouter (future routing)** | Lightweight OpenRouter integration / routing tooling to watch | Relevant if Nodehome later adds a cheap cloud fallback or multi-model routing layer |

Working architectural framing:

- `Connectors` for actual service/system access
- `Manuals` (skills / repo-local guidance) for gotchas, workflow rules, and learned operating knowledge

This is a useful way to think about MCP vs skills in the Sovereign Node stack: not either/or, but connector layer plus knowledge layer.

## Knowledge Management
| Tool | Purpose | Notes |
|------|---------|-------|
| **Obsidian** | Knowledge base viewer/editor | Karpathy workflow: raw/ -> wiki/ compilation |
| **Obsidian Web Clipper** | Article -> markdown conversion | Feed into raw/ directory |

## Research Tools
| Tool | Purpose | Notes |
|------|---------|-------|
| **AutoResearch** | Autonomous ML experiments | Karpathy's repo, single-GPU experiments |
| **Nanochat** | LLM training pipeline | Full pipeline: tokenize -> pretrain -> finetune -> serve |
| **Daily research sweeps** | Watch key feeds, repos, and blogs | Proposed: generate digests and promote only top items into `raw/` |
| **LLM weekly synthesis** | Future local rollup generation | Once Ollama is online, use local inference to synthesize weekly sweep rollups from daily digests |

Key public builders to watch in this stack: Georgi Gerganov / `llama.cpp`, Tim J. Baek / Open WebUI, and the LM Studio team.

Current W15 stack signals:

- `llama.cpp` split-mode/tensor work is active but still experimental, so it informs benchmarks rather than the day-one install plan.
- `vLLM` CPU KV cache offload is worth testing against the 3x RTX 3090 + 128GB RAM topology.
- Ollama remains the target first-run serving layer; Gemma4 needs an FA compatibility gate before being treated as stable on the node.
- Cheap 10GbE switching is bookmarked for future multi-node expansion, not a day-one purchase.

Current 2026-04-14 pressure note:

- Ollama `v0.20.7` and `v0.20.8` landed quickly enough to put pressure on the current `v0.20.5` target-install assumption.
- The right response is not to churn the bootstrap immediately. Keep `v0.20.5` pinned until the newer releases are reviewed for Gemma4 renderer changes, Ampere behavior, and RTX 3090 compatibility implications.
- Until that review is done, treat the install target as held under review rather than quietly outdated.

Current 2026-04-16 watch note:

- `llama.cpp` landed CUDA changes around explicit P2P opt-in and NCCL communicator management. That is directly relevant to future multi-GPU benchmarking, but it still argues for caution rather than redesign.
- Treat these as benchmark variables for direct `llama.cpp` testing on the 3x RTX 3090 node, not as reasons to move day-one serving away from the current `Ollama -> vLLM -> direct llama.cpp benchmark` order.
- Simon Willison's recent Datasette releases are interesting as lightweight local data-view tooling, but they are workflow-adjacent. They do not change the node bring-up plan.

Current 2026-04-17 candidate note:

- `Qwen3.5-35B-A3B` is worth tracking as a future vLLM benchmark candidate because the MoE shape could be attractive for local serving experiments.
- Do not let that change the current bring-up order or the day-one model list yet. Treat it as a later test case once the node is stable and the baseline serving stack is validated.

Current 2026-04-17 pressure note:

- `Ollama v0.21.0` materially increases pressure on the current `v0.20.5` install target.
- The posture is still conservative: do not auto-upgrade the bootstrap target blindly, but review `v0.21.0` before hardware bring-up rather than treating `v0.20.5` as settled.
- `Qwen3.6-35B-A3B` now looks more credible as a future local-model experiment, but it still belongs in the post-bring-up vLLM benchmark queue, not the day-one default stack.

Current 2026-04-18 pressure note:

- `vLLM v0.19.1` is now worth reviewing because the planned serving stack was already pinned to `v0.19.0`.
- This does not force a change yet, but it means the first install should choose deliberately between `v0.19.0` and `v0.19.1` instead of treating the earlier pin as settled.
- Recent `llama.cpp` CUDA graph and Gemma4 model-shape changes are still watch items for later direct benchmarking, not reasons to change day-one serving order.

Current 2026-04-20 fallback note:

- `Kimi K2.6` is open source and important enough to track as both a future local/runtime evaluation target and a cloud fallback candidate.
- The clean local support path appears to be `vLLM`, `SGLang`, or `KTransformers`; local `Ollama` / `llama.cpp` support is not established.
- Despite that, it is still not a practical local target for the current 3x3090 + 128GB RAM node because the model is too large to treat as a normal day-one deployment.

Current 2026-04-21 routing/watch note:

- `llm-openrouter 0.6` is worth watching as future routing/fallback tooling now that cheap model-routing candidates are becoming more relevant to the broader Nodehome architecture.
- `llama.cpp` OOM retry behavior and Gemma-4 tensor-parallel fixes are directly relevant to later benchmarking, but they still reinforce the same rule: direct `llama.cpp` remains a benchmark/watch path, not a day-one dependency for the 3x3090 box.
- `Ollama v0.21.1-rc0` is another sign that the `0.21.x` line is moving fast, but release candidates do not change the install target by themselves.

## Target Models (Day 1)

### Primary (Across 3 GPUs)
| Model | Size | Quantization | VRAM | Use Case |
|-------|------|-------------|------|----------|
| Llama 3.x 70B | 70B | Q6 | ~52GB (3 GPUs) | General intelligence, complex reasoning |
| DeepSeek-V3 | 70B+ | Q6-Q8 | ~52-70GB (3 GPUs) | Code, math, reasoning |

Future benchmark candidate:

- `Qwen3.5-35B-A3B` - promising MoE experiment for vLLM once the node is stable; not a day-one target
- `Qwen3.6-35B-A3B` - newer MoE benchmark candidate with encouraging local-use anecdotes; still not a day-one target
- `Kimi K2.6` - serious open frontier model to evaluate later; official local path exists, but it is not practical on the current 3x3090 node

### Cognitive Core (Single GPU)
| Model | Size | VRAM | Use Case |
|-------|------|------|----------|
| Gemma 4 26B MoE | 3.8B active | <12GB (1 GPU) | Fast responses, always-on agent |

### Swarm Architecture
- GPU 0: Cognitive core (Gemma 4 26B, always running)
- GPU 1-2: Large model (70B) for complex tasks, loaded on demand
- OR: 3 independent small models for parallel agent swarm
