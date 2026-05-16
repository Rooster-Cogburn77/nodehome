# Memory Architectures Watch

**Status:** Watch lane, not current implementation lane  
**Last updated:** 2026-05-16

This page tracks model-internal memory architectures that may become relevant to Nodehome later. These are not replacements for the current Nodechat memory path unless they produce a deployable runtime/checkpoint that beats the existing local baseline on real operator tasks.

## Current Nodehome Baseline

Nodechat's deployed memory stack is external retrieval plus provenance:

- AI History KB: private Claude/Codex/Claude Code history indexed in SQLite FTS.
- Repo context: bounded reads from known project files and runbooks.
- Web context: explicit and auto-routed public retrieval for fresh external facts.
- Live context: fixed Observe-tier checks against the homelab.
- Disclosure/audit: every routed block carries source/provenance and visible routing evidence.

That means the production comparison is not "small model with memory versus big model alone." It is:

- Experimental: small model with model-internal memory, often given only the question.
- Baseline: Nodechat `strong` profile (`Qwen/Qwen2.5-32B-Instruct-AWQ`) plus auto-routed history/repo/web/live context blocks, disclosure, and audit.

The evaluation axes are memory recall, base-model reasoning quality, provenance, safety, and operational fit.

## delta-mem / arXiv 2605.12357

**Paper:** `-mem: Efficient Online Memory for Large Language Models`  
**Date:** 2026-05-12  
**Links:** [arXiv abstract](https://arxiv.org/abs/2605.12357), [PDF](https://arxiv.org/pdf/2605.12357), [Qwen3-4B checkpoint](https://huggingface.co/declare-lab/delta-mem_qwen3_4b-instruct)

### What It Is

delta-mem is a serving/model-layer memory mechanism. The high-level design is:

- Keep the full-attention backbone frozen.
- Add a compact online associative-memory state matrix.
- Update that state during generation using a delta-rule learning step.
- Read from the memory state to generate low-rank corrections to the backbone attention computation.

Lineage: fast weights, Hebbian/delta-rule associative memory, test-time training, compressed-KV approaches, and SSM-adjacent memory systems such as the broader RWKV/Mamba/RetNet family of "small state instead of full attention history" ideas.

### Nodehome Decision

Watch it. Do not pivot the stack.

Reasons:

- The available artifact is a Qwen3-4B-class checkpoint, while Nodechat's strong local profile is a 32B AWQ model served through vLLM.
- A 4B model with clever memory is not automatically better than a 32B model with retrieval, stronger base reasoning, and provenance.
- This is model-internal generation-time memory, not a durable cross-session project knowledge base.
- It does not preserve source provenance, operator audit trail, or the explicit "what evidence was used" behavior Nodechat depends on.
- Using it in production would require runtime/checkpoint support, not a normal Open WebUI tool, Nodechat router, or RAG change.

If a future test shows delta-mem-Qwen3-4B beats vanilla Qwen3-4B but still loses to Nodechat `strong` plus AI History KB/RAG, that is a hold, not an adopt.

### Revisit Triggers

Re-evaluate when one or more of these happens:

- Independent reproduction by another lab or credible practitioner.
- A Qwen2.5/Qwen3 30B-class or larger delta-mem checkpoint appears.
- vLLM, SGLang, TGI, or Ollama support appears in a usable form.
- A real Nodechat workflow exposes a context-length/memory problem that AI History KB retrieval cannot solve.
- The runtime becomes simple enough to sandbox without destabilizing the production local stack.

### Local Benchmark Idea

Nodehome has an unusually good benchmark source: the AI History KB has hundreds of thousands of indexed private project-history items with source provenance. That enables an operator-domain memory test instead of relying only on synthetic memory benchmarks.

Example benchmark prompt:

> What did we decide about GPU2 and the pigtail rule?

Compare:

- `delta-mem` small model given the question alone.
- Nodechat `strong` profile given the question plus auto-routed history/repo context and disclosure.

Score correctness and evidence quality separately. A memory answer that is right but cannot cite or expose evidence is still weaker for operator use than a sourced Nodechat answer.
