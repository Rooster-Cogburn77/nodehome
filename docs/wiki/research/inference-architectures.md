# Inference Architectures Watch

**Status:** Watch lane, not current implementation lane  
**Last updated:** 2026-05-16

This page tracks serving and decoding architectures that may affect Nodehome's local model stack. The bar for adoption is higher than "interesting paper": it needs a usable runtime path, a model/checkpoint relevant to our size class, and a win against the validated local baseline.

## Current Nodehome Baseline

Validated local serving lanes:

- `fast`: `mistral-small3.1:24b` on Ollama, single RTX 3090, `51.13 tok/s`.
- `strong`: `Qwen/Qwen2.5-32B-Instruct-AWQ` on vLLM TP=2, GPUs 0/1, `59.13 tok/s`.
- `deep`: `llama3.3:70b-instruct-q4_K_M` on Ollama layer-split, GPUs 0/1, roughly `8-15 tok/s`.

GPU2 remains excluded from sustained work until the proper SF-1600F14HT cable arrives and the temporary pigtail rule is retired.

## Orthrus / arXiv 2605.12825

- **Source:** GitHub repo + arXiv paper + Hugging Face checkpoints.
- **Links:** [GitHub](https://github.com/chiennv2000/orthrus), [arXiv](https://arxiv.org/abs/2605.12825), [Orthrus-Qwen3-8B](https://huggingface.co/chiennv/Orthrus-Qwen3-8B)
- **Published:** 2026-05-12
- **Confidence:** Primary artifact exists, but performance claims are not locally reproduced.
- **Novelty:** Dual-view decoding architecture: a frozen autoregressive base model plus a lightweight trainable diffusion view that generates tokens in parallel while sharing the same KV cache. The authors claim strictly lossless generation fidelity, O(1) extra KV-cache overhead, and up to 7.8x speedup.
- **Available models:** Qwen3-backed Orthrus checkpoints at 1.7B, 4B, and 8B. The repo table lists average speedups around 4.25x, 5.20x, and 5.36x respectively.
- **Action:** Watch lane. Do not deploy into Nodehome now. Re-evaluate when native vLLM/SGLang support is real and when a checkpoint exists at a size/quality tier that matters to the current stack.

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
- A bounded single-GPU local smoke can compare Orthrus-Qwen3-8B against the existing Ollama `qwen3:8b` smoke lane without touching GPU2.

### Possible Future Benchmark

If the runtime matures, test it as an isolated experiment:

- Baseline: existing `qwen3:8b` or another Qwen3 8B lane on one RTX 3090.
- Candidate: `chiennv/Orthrus-Qwen3-8B` on one RTX 3090.
- Metrics: tokens/sec, prompt eval speed, peak VRAM, output identity/fidelity against baseline prompts, cold-load time, and whether streaming behavior is acceptable.
- Gate: no production routing until it is served through a normal OpenAI-compatible endpoint with audited startup/health behavior.

### Why It Matters

If the lossless parallel-decoding claim holds at larger model sizes and lands in vLLM/SGLang, it could be a real serving-layer improvement: faster local inference without changing Nodechat's user-facing architecture. Today it is a research/runtime watch item, not a replacement for the validated vLLM AWQ lane.
