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

### 2026-05-11 — Article titles swallowed (replaced by site nav title)

**Symptom:** in the 2026-05-11 core digest, the vLLM blog post is listed as "Blog | vLLM" with no actual post title or content snippet. That's the page's HTML `<title>` element capturing the site nav header instead of the specific post heading.

**Probable root cause:** the RSS/Atom fetcher is reading the wrong DOM element when the source is a multi-post blog page vs. a per-post RSS entry. May affect any source that doesn't expose per-post RSS items cleanly.

**Action items:**
- Identify the specific fetcher path used for the vLLM blog source in `sweeps/sources.json` (or wherever sources are defined).
- Add per-source overrides if a site doesn't expose clean RSS — point at a specific feed URL or scrape a different DOM selector.
- Check whether other "established primary" sources are exhibiting the same swallowed-title issue and would benefit from the same fix.

### Pre-existing — X/OpenRSS social feed health degraded

**Symptom:** repeatedly across recent sweeps, 6-21 social feed fetches fail per run; cached state used as fallback. The 2026-05-09 extended run logged 21 failures (mostly timeouts); 2026-05-11 core logged 6.

**Probable root cause:** X's API access policy + OpenRSS fallback reliability. Already known operationally (recorded in Session 14 area).

**Action items:**
- The 2026-05-05 sweep noted this as "lower-confidence evidence" — that classification should continue to apply to any sweep with >5 social feed failures.
- Consider de-emphasizing or temporarily disabling the social-primary lane in the synthesizer's input until source health recovers.
- Not actionable beyond filing; X's policy is the rate-limiter, not the pipeline.

---

## Resolved

(none yet)
