# Session Scratch - 2026-05-09 / 2026-05-10 (Session 14)
Focus: Post-bring-up software stack expansion. Interactive A/B, Open WebUI, Docker + GPU passthrough, vLLM staging.

## Observed (validated this session)
- 30B-class A/B benchmark (single 3090, same prompt, `--verbose`):
  - `mistral-small3.1:24b`: `eval 51.13 tok/s`, `prompt eval 1501.38 tok/s`, `load 6.72 s`. Winner.
  - `gemma3:27b`: `eval 39.91 tok/s`, `prompt eval 411.74 tok/s`, `load 28.25 s`.
  - `qwen2.5:32b-instruct-q4_K_M`: `eval 39.21 tok/s`, `prompt eval 677.02 tok/s`, `load 8.07 s`.
- Mistral 24B is the new default daily-driver interactive model.
- 5 models on disk, ~98 GB total: qwen3:8b, mistral-small3.1:24b, gemma3:27b, qwen2.5:32b-instruct-q4_K_M, llama3.3:70b-instruct-q4_K_M.
- Docker `29.1.3` installed; user added to `docker` group (effective on next login; `sudo docker` for now).
- Open WebUI Docker container on port `3000`, pointed at local Ollama. Browser access works, dropdown populated.
- Ollama systemd override at `/etc/systemd/system/ollama.service.d/override.conf` sets `OLLAMA_HOST=0.0.0.0:11434`. Required for Docker containers to reach Ollama via `host.docker.internal`.
- `nvidia-container-toolkit 1.19.0` installed; `nvidia` registered as Docker runtime; `nvidia-smi` works inside containers with all 3 GPUs visible.
- `vllm/vllm-openai:v0.19.1` Docker image pulled. Container launched bound to GPUs 0+1 only (per pigtail rule on GPU 2), serving `Qwen/Qwen2.5-32B-Instruct-AWQ` on TP=2 with `--gpu-memory-utilization 0.85` and `--max-model-len 8192`. OpenAI-compatible API on port `8000`. Model download/load still in progress at time of this commit.

## Decisions made this session
- Default interactive model is `mistral-small3.1:24b`. Speed delta over the others is large enough to feel; quality re-evaluation can happen later if needed.
- vLLM running with TP=2 only (not TP=3). GPU 2 stays out of vLLM scope until the proper cable arrives and the temporary pigtail rule is retired.
- Model for the first vLLM benchmark is the publicly-available `Qwen/Qwen2.5-32B-Instruct-AWQ` (no HF gate), not a Llama 3.3 70B variant. The 70B comparison comes later either via an ungated 70B AWQ (`Qwen/Qwen2.5-72B-Instruct-AWQ`) on TP=3, or after handling the HF token gate for Llama 3.3.
- Operational paste workaround: long single-line shell commands wrap badly on this terminal and can silently break heredocs and piped `tee` commands. Workaround: stash long strings in shell variables, keep each typed line short.

## Not Proved (still ahead of the build)
- vLLM TP=2 token rate vs Ollama baselines. Pending model load.
- Sustained 3-GPU heavy inference. Gated on the cable arriving and the pigtail being retired.
- vLLM TP=3 on a 70B-class model.
- 70B Q6 across all 3 GPUs.
- Sweeps pipeline wired to local model for synthesis (the project's stated goal of automated research).
- Sustained thermal validation under multi-hour load.
- ReBAR enable + A/B vs current `[Disabled]`.
- Final physical deployment: rails, rack mount, cable management, dedicated IPMI patch, permanent location move. Deferred until cable arrives.

## Live status of major services
- `ollama.service` — active, bound to `0.0.0.0:11434`
- `docker.service` — active, with nvidia runtime registered
- `open-webui` container — up, port 3000, points at host Ollama
- `vllm-server` container — up (detached), port 8000, mid-load on `Qwen/Qwen2.5-32B-Instruct-AWQ` at the time of this commit

## Next physical step
- Wait for cable. Realistic window 2026-05-23 to 2026-06-10. Continuing to look for faster source in parallel.

## vLLM benchmark complete
- vLLM `v0.19.1` on `Qwen/Qwen2.5-32B-Instruct-AWQ`, TP=2 across GPUs 0+1, awq_marlin kernel + FA2: **`59.13 tok/s`** end-to-end (795 completion tokens in 13.445 s wall clock).
- ~50% faster than Ollama on the same 32B class (39.21 tok/s GGUF Q4_K_M).
- ~4-7× faster than Ollama 70B Q4 layer-split (~8-15 tok/s).
- Day-one stack pin (vLLM for multi-GPU production tier) empirically validated.

## Next software step
- Wire the existing `sweeps/` pipeline to use the local Ollama (or vLLM) for synthesis. Project's stated automated-research goal.
- TP=3 + `Qwen/Qwen2.5-72B-Instruct-AWQ` benchmark is gated on GPU 3 being unrestricted (cable arrival).
