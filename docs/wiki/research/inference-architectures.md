# Inference Architectures Watch

**Status:** Watch lane, not current implementation lane  
**Last updated:** 2026-05-18

This page tracks serving and decoding architectures that may affect Nodehome's local model stack. The bar for adoption is higher than "interesting paper": it needs a usable runtime path, a model/checkpoint relevant to our size class, and a win against the validated local baseline.

## Current Nodehome Baseline

Validated local serving lanes:

- `fast`: `mistral-small3.1:24b` on Ollama, single RTX 3090, `51.13 tok/s`.
- `strong`: `Qwen/Qwen2.5-32B-Instruct-AWQ` on vLLM TP=2, GPUs 0/1, `59.13 tok/s`.
- `deep`: `llama3.3:70b-instruct-q4_K_M` on Ollama layer-split, GPUs 0/1, roughly `8-15 tok/s`.

GPU2 remains excluded from sustained work until the proper SF-1600F14HT cable arrives and the temporary pigtail rule is retired.

## SANA-WM / arXiv 2605.15178

- **Source:** NVIDIA/NVlabs project page, arXiv paper, Hugging Face paper page, and `NVlabs/Sana` repo update surfaced 2026-05.
- **Links:** [Project](https://nvlabs.github.io/Sana/WM/), [GitHub](https://github.com/NVlabs/Sana), [arXiv](https://arxiv.org/abs/2605.15178), [Hugging Face paper page](https://huggingface.co/papers/2605.15178)
- **Published:** 2026-05-14
- **Confidence:** Primary paper and repo announcement exist. Local run path is not yet validated on Nodehome.
- **What it is:** 2.6B controllable world/video model for 720p minute-scale generation from an input image, text prompt, and 6-DoF camera trajectory. It is useful to track as a future synthetic-scene/video/world-model workload, not as a replacement for the validated LLM serving stack.
- **Current claims:** Training on about 213K public video clips in 15 days on 64 H100s; stronger one-minute action-following than prior open baselines; comparable visual quality at 36x higher throughput in the authors' benchmark; distilled variant can run on a single RTX 5090 with NVFP4 quantization and denoise a 60s 720p clip in about 34s.
- **Caution:** "World model" here does not mean a validated physics simulator or robotics environment. It is a generative video/world model with camera control. The strongest consumer-GPU claim depends on RTX 5090-class Blackwell NVFP4 behavior, so it does not transfer cleanly to Nodehome's RTX 3090s. Do not turn social-media claims about autonomous simulation loops into local capability claims without a local run.
- **Action:** Add to the watch/use-candidate lane. Do not install into the production stack yet. A bounded lab test is allowed only after official SANA-WM weights/docs are clearly runnable, and it must use a disposable container or lab directory, avoid private data mounts, keep GPU2 unused while the temporary pigtail rule is active, and stop/restart any conflicting serving containers deliberately.

### Nodehome Decision

Watch it and preserve an optional lab path. No production service change today.

Reasons:

- The current validated production lanes are Ollama/vLLM LLM serving; SANA-WM is a separate video-generation workload.
- vLLM/Open WebUI/Nodechat do not get SANA-WM support automatically from the SANA repo existing.
- Nodehome's RTX 3090s lack Blackwell NVFP4 acceleration, so the RTX 5090 inference claim is a future hardware signal, not proof this will perform well on the current cards.
- A SANA-WM test would compete with current GPU memory/service allocation and must not touch GPU2 until the pigtail rule is retired.

### Revisit Triggers

Re-evaluate when one or more of these happens:

- Official SANA-WM inference docs and weights are published with a reproducible single-GPU path.
- Community or upstream reports show successful Ampere/RTX 3090 runs with concrete VRAM, latency, and quality notes.
- A ComfyUI, Diffusers, or containerized runner lands that does not require broad host-environment changes.
- Nodehome obtains a Blackwell GPU such as an RTX 5090 and deliberately wants a separate single-GPU world/video lane.
- A real project use case appears: synthetic scene generation, camera-path video generation, robotics/simulation ideation, or media-pipeline experiments.

### Lab-Only Benchmark Gates

Hard gates before running:

- Stop `vllm-server` only if needed, record the stop/restart, and verify the normal LLM stack recovers afterward.
- Do not use GPU2 while the temporary pigtail rule is active.
- Prefer disposable Docker or a dedicated lab directory over modifying the host Python environment.
- Do not mount private project data, KeePass vaults, credentials, inboxes, or customer/subscriber material into the lab container.
- Keep downloaded weights, generated videos, benchmark logs, and dependency scratch files out of git.
- Time-box setup. If CUDA/PyTorch/video dependency resolution becomes unstable, stop and log the blocker rather than churning the production node.

## SubQ / Subquadratic Sparse Attention

- **Source:** Subquadratic vendor materials + Appen benchmark whitepaper surfaced 2026-05-16.
- **Links:** [SubQ research page](https://subq.ai/research/ssa), [SSA technical note](https://subq.ai/how-ssa-makes-long-context-practical), [Appen whitepaper landing page](https://www.appen.com/whitepapers/benchmarking-subquadratics-latest-model-ssa-kernel)
- **Status:** Hosted/API long-context architecture watch item, not a local Nodehome serving change.
- **Current claims:** 12M-token product positioning, OpenAI-compatible API path, content-dependent sparse attention, and third-party/Appen-reported SSA kernel speedups over dense FlashAttention-style processing at very long context. Subquadratic's current public tables report `95.6%` RULER at 128K, `86.2%` MRCR v2 at 1M, and `81.8%` SWE-Bench Verified for SubQ 1M-Preview.
- **Caution:** This is still closed/private-beta infrastructure. The Appen result is a commissioned third-party evaluation, not public peer review or an independently reproducible open checkpoint. Broader model-card coverage, pricing, safety/general-reasoning benchmarks, and public-leaderboard placement remain watch triggers.
- **Action:** Keep in the hosted-routing watch lane. Do not replace Nodechat AI History/RAG or the validated local vLLM/Ollama stack. If early access opens, run a small Nodehome eval against real repo/history tasks: prior-decision retrieval, multi-file code reasoning, full-repo summarization, latency, and cost versus Nodechat `strong` plus auto-routed AI History/repo context.

## Orthrus / arXiv 2605.12825

- **Source:** GitHub repo + arXiv paper + Hugging Face checkpoints.
- **Links:** [GitHub](https://github.com/chiennv2000/orthrus), [arXiv](https://arxiv.org/abs/2605.12825), [Orthrus-Qwen3-8B](https://huggingface.co/chiennv/Orthrus-Qwen3-8B)
- **Published:** 2026-05-12
- **Confidence:** Primary artifact exists, but performance claims are not locally reproduced.
- **Novelty:** Dual-view decoding architecture: a frozen autoregressive base model plus a lightweight trainable diffusion view that generates tokens in parallel while sharing the same KV cache. The authors claim strictly lossless generation fidelity, O(1) extra KV-cache overhead, and up to 7.8x speedup.
- **Available models:** Qwen3-backed Orthrus checkpoints at 1.7B, 4B, and 8B. The repo table lists average speedups around 4.25x, 5.20x, and 5.36x respectively.
- **Action:** Watch lane. Do not deploy into Nodehome now. A bounded lab-only benchmark is allowed as evidence gathering, but it must not create a production Nodechat profile or serving change. Re-evaluate production only when native vLLM/SGLang support is real and when a checkpoint exists at a size/quality tier that matters to the current stack.

### What It Is In Plain Terms

Normal LLM decoding is serial: generate token 1, then token 2, then token 3. Orthrus tries to keep the exact same final behavior as the normal model while adding a second "diffusion" view that can propose/generate multiple future tokens in parallel. A consensus mechanism checks that the parallel path matches the base autoregressive model's distribution.

If the lossless claim holds, this is more interesting than the usual "fast but worse" diffusion-language-model story. It is closer to speculative decoding in goal, but the repo claims less redundant memory overhead because both views share the same KV cache.

### Nodehome Decision

Watch it. No stack change.

Reasons:

- The released checkpoints are Qwen3 1.7B/4B/8B-class. Nodechat's main `strong` profile is currently a 32B AWQ vLLM model.
- The repo README says native vLLM and SGLang integration is "coming soon"; the current quickstart uses `trust_remote_code=True` through Transformers.
- Hugging Face's generic vLLM/SGLang snippets do not prove that Orthrus diffusion mode works through those servers today; the repo itself still flags native integration as future work.
- `trust_remote_code=True` plus custom generation code is not something to drop into the production homelab path casually.
- GPU2 is still under the pigtail rule, so any local test must stay on a single unrestricted GPU or GPUs 0/1 only.

### Revisit Triggers

Re-evaluate when one or more of these happens:

- Native vLLM or SGLang integration ships and explicitly supports `use_diffusion_mode=True` or equivalent.
- A 24B/30B/32B-class checkpoint appears, or a recipe proves the method on Qwen2.5/Qwen3 models in Nodehome's quality tier.
- Independent reproduction confirms lossless outputs and real wall-clock speedup, not just paper/demo benchmarks.
- The model can run without broad `trust_remote_code=True` risk in the production serving path.
- A bounded single-GPU local smoke proves the method on this hardware without touching GPU2.

### Lab-Only Benchmark Gates

Optionality is useful, but this is a lab experiment only. It is not a production migration path and should not touch Nodechat routing unless later revisit triggers land.

Hard gates before running:

- Stop `vllm-server` for the experiment window, then restart it afterward and record both actions in the lab log. vLLM holds roughly 22.5 GiB on each of GPUs 0 and 1 under the current 0.85 utilization posture, so Orthrus on those cards will otherwise collide with production serving.
- Do not use GPU2 while the temporary pigtail rule is active.
- Prefer a throwaway Docker container over a host venv. The current quickstart requires `trust_remote_code=True`, which runs arbitrary Python from the model repo; container isolation with minimal mounts is the correct trust boundary.
- Do not mount private project data into the container. Use a disposable lab path such as `/tmp/orthrus-lab` or `~/orthrus-lab`.
- Do not commit lab artifacts, downloaded weights, raw benchmark output, or dependency scratch files to git. Commit only a concise result note if the experiment produces useful evidence.
- Time-box dependency setup at 4 hours. If CUDA/PyTorch/flash-attn/Transformers dependency resolution fails, stop and log that the Orthrus install path was not stable on the current CUDA 13.2 / driver 595 stack as of the test date.

Measurement order:

1. Correctness first: compare `chiennv/Orthrus-Qwen3-8B` against vanilla Qwen3-8B through the same Transformers + flash-attn path, deterministic `temperature=0`, at least 10 prompts, and require token-for-token output match before treating speed numbers as meaningful.
2. Throughput second: only after the correctness gate passes, measure tokens/sec, prompt eval speed, peak VRAM, cold-load time, errors, and streaming behavior.
3. Scope conclusion: a successful Qwen3-8B Orthrus run validates the watch-lane thesis on Nodehome hardware only. It still does not replace the validated `strong` lane until a 24B/30B/32B-class checkpoint and native vLLM/SGLang/OpenAI-compatible serving path exist.

### Why It Matters

If the lossless parallel-decoding claim holds at larger model sizes and lands in vLLM/SGLang, it could be a real serving-layer improvement: faster local inference without changing Nodechat's user-facing architecture. Today it is a research/runtime watch item, not a replacement for the validated vLLM AWQ lane.
