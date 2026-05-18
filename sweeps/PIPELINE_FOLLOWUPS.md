# Sweeps Pipeline - Known Issues and Follow-ups

Tracking items for the daily/extended/weekly sweep pipeline that need attention but are not urgent enough to block on. Add new items at the top with the date and origin. Resolve items by moving them under "Resolved" with the commit reference.

---

## Open

(none currently)

---

## Resolved

### 2026-05-18 - X/OpenRSS social feed degradation

Resolved by making X/OpenRSS an explicit transport instead of an automatic scheduled dependency.

**Original symptom:** recent sweeps repeatedly logged 6-21 X/OpenRSS social feed failures per run. Core X sources retried after cooldown, failed again, and emitted cached-state health rows; extended X sources accumulated long quarantine lists with OpenRSS 403/429/timeouts. This made scheduled health look broken even when durable sources were healthy.

**Fix:** `x_user` sources are now skipped unless `X_BEARER_TOKEN` exists or `SWEEP_OPENRSS_FALLBACK_ENABLED=true` is explicitly set. Skipped X transport clears stale degraded failure counts and appears as `Skipped` in the health report rather than `Cached`, `Failed`, or `Quarantined`. The status reporter excludes intentional `skipped` transport from degraded/non-ok counts.

**Validation:** `tests/test_sweeps_digest_quality.py` covers default OpenRSS-off behavior and verifies skipped X transport clears prior degraded failure state.

### 2026-05-18 - vLLM blog title-swallow

Resolved by vLLM-specific page parsing in `sweeps/run_daily.py` and the source URL update in `sweeps/sources.json`.

**Original symptom:** core digests listed the vLLM blog source as `Blog | vLLM` instead of the actual article titles. This hid real serving-layer signals such as TurboQuant, Mooncake/disaggregated KV cache, and VeRL-Omni.

**Fix:** the `vllm-blog` source now points at `https://vllm.ai/blog`, and `parse_page()` uses a vLLM-specific blog-card parser that extracts article links, titles, publish dates, and summaries instead of the document `<title>`.

**Validation:** `tests/test_sweeps_digest_quality.py` covers vLLM blog-card extraction and verifies `Blog | vLLM` is not emitted for the fixture.

### 2026-05-18 - Synthesis boilerplate

Resolved for the local heuristic summary path and tightened for optional LLM synthesis prompts.

**Original symptom:** daily summaries repeated stock phrases such as "Busy day across multiple parts of the stack", "A few things moved today", "No single breakthrough", and "small CUDA changes can compound quickly in local inference stacks".

**Fix:** `heuristic_summary()` no longer pads to four sentences with generic filler, no longer opens with canned day-level framing, and now emits only source-anchored item sentences plus a specific fetch-degradation sentence when relevant. The optional AI summary prompt in `run_daily.py` and `sweeps/llm_synthesize.py` now explicitly bans the known filler phrases and requires source-item anchoring.

**Validation:** `tests/test_sweeps_digest_quality.py` covers a mixed vLLM/llama.cpp input and asserts the summary includes the concrete vLLM item while excluding the known boilerplate phrases.

### 2026-05-18 - Consumer-gaming hardware false positives

Resolved by a hardware-lane exclusion filter in `sweeps/run_daily.py`.

**Original symptom:** consumer-gaming items such as PlayStation, GTA, Steam Controller, handheld console, and game benchmark posts were entering the hardware lane as if they were relevant to the owned-hardware AI stack.

**Fix:** hardware items with consumer-gaming terms are filtered unless they also include a stack-relevant hardware term such as EPYC, Supermicro, RDIMM, ECC, BMC/IPMI, server/workstation, local inference, CUDA/ROCm, PCIe, NVMe, 10GbE, or similar build-relevant context.

**Validation:** `tests/test_sweeps_digest_quality.py` covers a PlayStation handheld item being filtered while a Memtest86+ platform-support item remains eligible.

### 2026-05-18 - Partial-keyword topic mis-tags

Resolved for the confirmed power/thermal false-positive class in `sweeps/run_daily.py`.

**Original symptom:** shallow substring matches could stamp workflow content with the wrong topic, for example a powerful LLM CLI/shebang-line item being tagged as a power/thermal topic.

**Fix:** the helper now uses word/phrase-aware matching. Power/thermal classification requires a real power/thermal term or `power` plus hardware context, so words like `powerful` do not trip the rack/PSU classification. Network `switch` matching also uses word boundaries so unrelated words do not trip networking hardware.

**Validation:** `tests/test_sweeps_digest_quality.py` covers the `powerful LLM CLI trick for shebang lines` false positive and verifies it does not produce the power/thermal why-line.

### 2026-05-18 - GitHub activity feed duplicate entries

Resolved by digest-quality hardening in `sweeps/run_daily.py`.

**Original symptom:** in the 2026-05-12 core digest, the Simon Willison GitHub activity entry `simonw pushed llm` appeared 8+ times as separate rows with identical text. The 2026-05-18 core digest repeated the same failure mode with `watchfiles` activity.

**Fix:** GitHub activity entries now collapse by source, lane, action, target, and published date. Repeated pushes/contributions/PR activity render as one counted row; low-value branch/star/comment-only activity is dropped from the digest body.

**Validation:** `tests/test_sweeps_digest_quality.py` covers duplicate `simonw pushed watchfiles` entries collapsing to one row and low-value `created a branch` activity being excluded.

### 2026-05-18 - Social direct-post validation noise

Resolved by digest-quality hardening in `sweeps/run_daily.py`.

**Original symptom:** social-primary rows with no discovered follow-up URL rendered repeated `Validation: direct-post` lines in email output even though there was no actionable validation queue item.

**Fix:** social-primary items without discovered follow-up URLs now use `validation_status = n/a`, so the digest body does not render repeated direct-post validation lines. Social-primary sources are also down-ranked behind primary infra/workflow sources unless a follow-up URL exists.

**Validation:** `tests/test_sweeps_digest_quality.py` covers social-primary validation status with no discovered URL and verifies social-primary hardware does not outrank primary infra.

### 2026-05-18 - Top-signal release-series repetition

Resolved by digest-quality hardening in `sweeps/run_daily.py`.

**Original symptom:** consecutive `llama.cpp` release tags could occupy most of Top Signals, producing low-information headers such as `b9209`, `b9208`, `b9204`, and `b9203`.

**Fix:** top-signal and synthesis candidate selection now run through a digest-level signature dedupe pass. `llama.cpp` release tags collapse to one representative release-series signal, while substantive commit entries can still appear separately.

**Validation:** `tests/test_sweeps_digest_quality.py` covers release-series collapse while preserving a distinct llama.cpp CUDA commit row.
