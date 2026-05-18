# Sweeps Pipeline — Known Issues and Follow-ups

Tracking items for the daily/extended/weekly sweep pipeline that need attention but aren't urgent enough to block on. Add new items at the top with the date and origin. Resolve items by moving them under "Resolved" with the commit reference.

---

## Open

### 2026-05-11 — Synthesis produces repetitive boilerplate

**Symptom:** the same canned phrases appear across multiple days' digests. Observed example: "small CUDA changes can compound quickly in local inference stacks" appeared verbatim in the 2026-05-09 extended, 2026-05-10 extended, and 2026-05-11 core digests. The synthesizer is reusing template-feeling text rather than producing differentiated reads.

**Probable root cause:** the synthesis prompt (in `sweeps/llm_synthesize.py`) is too generic, so when the brief contains thin signal the model defaults to safe filler. Alternatively, the model itself is pattern-matching to a small set of "synthesis-style" phrases regardless of input.

**Action items:**
- Review the synthesis prompt; add explicit "avoid generic phrases" instruction or force the model to anchor each sentence to a specific source line.
- Consider lowering `temperature` further (currently 0.2) or raising it slightly to break out of the rut.
- A/B test against a different daily-driver model (e.g., `mistral-small3.1:24b` vs `qwen2.5:32b-instruct-q4_K_M`) to see if the boilerplate is model-specific or prompt-specific.

### 2026-05-11 — Consumer-gaming items mis-classified as relevant hardware

**Symptom:** the keyword classifier is tagging consumer-gaming hardware news as "hardware" for the Sovereign Node digest. Examples from the 2026-05-09 extended digest: "Sony is telling PS4 owners to buy a PS5 for GTA 6," "Sony says PlayStation 6 launch timing and price are not decided," "Valve fixes Steam Controller trackpad," "007 First Light needs RTX 4080 or RX 7900 XTX for native 4K 60 FPS," "Lian Li launches HydroShift II OLED Curved 360 AIO with 6.67-inch display."

**Probable root cause:** the keyword/category classifier is matching on broad terms like "GPU," "RTX," "VRAM," "DDR" without an exclusion pass for gaming-context terms (PlayStation, GTA, Steam, Valve, AIO cooler, console).

**Action items:**
- Add a "consumer gaming exclusion" filter pass to the classifier. Keywords like `PlayStation`, `PS5`, `PS6`, `Xbox`, `GTA`, `Steam Controller`, `Steam Deck`, `AIO` (in chassis/cooler context), `Roblox`, `Switch 2` should down-rank or exclude items unless paired with stack-relevant terms.
- Consider a positive-signal allow-list for hardware items: must mention `EPYC`, `Threadripper`, `Xeon`, `MI300`, `H100`, `A100`, `V100`, `RTX 3090`, `RTX 4090`, `DDR4 ECC RDIMM`, `vLLM`, `Ollama`, `llama.cpp`, `inference`, `tensor parallel`, etc. — to be relevant to this build's lane.

### 2026-05-11 — Article titles swallowed (replaced by site nav title) [RECURRING]

**Symptom:** in the 2026-05-11 core digest AND the 2026-05-12 core digest, the vLLM blog post is listed as "Blog | vLLM" with no actual post title or content snippet. That's the page's HTML `<title>` element capturing the site nav header instead of the specific post heading. **Confirmed recurring on consecutive days, not transient.**

**What the swallowed content actually was** (retrieved manually 2026-05-12 from https://vllm.ai/blog):
- "A First Comprehensive Study of TurboQuant: Accuracy and Performance" (2026-05-11) — KV-cache quantization method using low bit-width. Directly relevant to this build's production posture (vLLM at `--gpu-memory-utilization 0.85`; better KV-cache compression unlocks more context length or more concurrent requests in the same VRAM).
- "vLLM Tops the Artificial Analysis Leaderboard" (2026-05-11) — positioning post; notable for calling out Qwen 3.5 397B as a leading-edge model with good vLLM support.
- "Serving Agentic Workloads at Scale with vLLM x Mooncake" (2026-05-06) — Mooncake distributed KV cache, 3.8x throughput claim. Multi-node relevance.

This is two consecutive days where the digest's only vLLM signal was a title-and-content-stripped placeholder while the actual blog had three substantive posts.

**Probable root cause:** the RSS/Atom fetcher is reading the wrong DOM element when the source is a multi-post blog page vs. a per-post RSS entry. Note: `https://blog.vllm.ai/` 301-redirects to `https://vllm.ai/blog` — the redirect may also be confusing the fetcher.

**Action items:**
- Identify the specific fetcher path used for the vLLM blog source in `sweeps/sources.json`. Update to the post-redirect URL `https://vllm.ai/blog`.
- Add per-source overrides if a site doesn't expose clean RSS — point at a specific feed URL or scrape a different DOM selector.
- Check whether other "established primary" sources are exhibiting the same swallowed-title issue and would benefit from the same fix.
- Until fixed: manually check the vLLM blog at least weekly since the digest can't be trusted to surface posts.

### 2026-05-12 — Keyword classifier mis-tags content based on partial term matches

**Symptom:** the keyword classifier is matching on partial term occurrences without enough context, leading to wildly wrong topic tags. Examples from the 2026-05-12 core digest:
- "New TIL: I figured out how to use my LLM CLI tool in a shebang line..." → tagged as **"Power or thermal topic — relevant to the 1600W PSU and blower cooling config."** The classifier matched on "LLM" or some other term and routed to the power/thermal bucket. The actual content is a workflow item.
- "This is excellent. I particularly like the definition of the 'Zombie Internet'..." → tagged as **"Agent or tool-use pattern — relevant to local AI workflow automation."** It's a quote post / meta commentary, not an agent/tool-use signal.

This is a different class of issue from the consumer-gaming mis-classification filed 2026-05-11 — that one was over-broad inclusion (consumer gaming items reaching the hardware bucket); this one is wrong-bucket routing on content that legitimately belongs in *some* bucket but not the one assigned.

**Probable root cause:** the topic-tag-assignment heuristic is using too-shallow keyword features without contextual disambiguation. "LLM" alone shouldn't route to power-thermal; it should require co-occurrence with thermal/power terms.

**Action items:**
- Audit the topic-tag dictionary / routing rules. Move from single-keyword triggers to keyword + context (require two or more terms from the same topical cluster).
- Consider a "did the LLM synthesizer actually flag this as relevant to topic X" cross-check before stamping a topic tag at digest-render time.
- Likely shares a root cause with the consumer-gaming mis-classification — the underlying classifier is too aggressive on shallow keyword matches across multiple failure modes.

### Pre-existing — X/OpenRSS social feed health degraded

**Symptom:** repeatedly across recent sweeps, 6-21 social feed fetches fail per run; cached state used as fallback. The 2026-05-09 extended run logged 21 failures (mostly timeouts); 2026-05-11 core logged 6.

**Probable root cause:** X's API access policy + OpenRSS fallback reliability. Already known operationally (recorded in Session 14 area).

**Action items:**
- The 2026-05-05 sweep noted this as "lower-confidence evidence" — that classification should continue to apply to any sweep with >5 social feed failures.
- Consider de-emphasizing or temporarily disabling the social-primary lane in the synthesizer's input until source health recovers.
- Not actionable beyond filing; X's policy is the rate-limiter, not the pipeline.

---

## Resolved

### 2026-05-18 — GitHub activity feed duplicate entries

Resolved by digest-quality hardening in `sweeps/run_daily.py`.

**Original symptom:** in the 2026-05-12 core digest, the Simon Willison GitHub activity entry "simonw pushed llm" appeared 8+ times as separate rows with identical text. The 2026-05-18 core digest repeated the same failure mode with `watchfiles` activity.

**Fix:** GitHub activity entries now collapse by source, lane, action, target, and published date. Repeated pushes/contributions/PR activity render as one counted row; low-value branch/star/comment-only activity is dropped from the digest body.

**Validation:** `tests/test_sweeps_digest_quality.py` covers duplicate `simonw pushed watchfiles` entries collapsing to one row and low-value `created a branch` activity being excluded.

### 2026-05-18 — Social direct-post validation noise

Resolved by digest-quality hardening in `sweeps/run_daily.py`.

**Original symptom:** social-primary rows with no discovered follow-up URL rendered repeated `Validation: direct-post` lines in email output even though there was no actionable validation queue item.

**Fix:** social-primary items without discovered follow-up URLs now use `validation_status = n/a`, so the digest body does not render repeated direct-post validation lines. Social-primary sources are also down-ranked behind primary infra/workflow sources unless a follow-up URL exists.

**Validation:** `tests/test_sweeps_digest_quality.py` covers social-primary validation status with no discovered URL and verifies social-primary hardware does not outrank primary infra.

### 2026-05-18 — Top-signal release-series repetition

Resolved by digest-quality hardening in `sweeps/run_daily.py`.

**Original symptom:** consecutive `llama.cpp` release tags could occupy most of Top Signals, producing low-information headers such as `b9209`, `b9208`, `b9204`, and `b9203`.

**Fix:** top-signal and synthesis candidate selection now run through a digest-level signature dedupe pass. `llama.cpp` release tags collapse to one representative release-series signal, while substantive commit entries can still appear separately.

**Validation:** `tests/test_sweeps_digest_quality.py` covers release-series collapse while preserving a distinct llama.cpp CUDA commit row.
