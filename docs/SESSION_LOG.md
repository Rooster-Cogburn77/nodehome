# Sovereign Node - Session Log
<!-- At the start of each month, move previous month's entries to docs/archives/SESSION_LOG_YYYY-MM.md -->

## 2026-04-14 (Session 5)
**Focus:** Sweep review, Ollama install-target pressure, software-stack posture
**What was done:**
- Reviewed the 2026-04-14 daily sweep for build-relevant signal instead of treating the digest as a changelog dump.
- Logged the main stack takeaway: Ollama `v0.20.7` and `v0.20.8` now pressure the current `v0.20.5` target-install assumption.
- Chose the conservative response: keep the bootstrap target at `v0.20.5` until the newer releases are reviewed specifically for Gemma4 renderer changes, Ampere behavior, and RTX 3090 implications.
- Confirmed that today's sweep does not change the serving hierarchy: Ollama remains the first inference path, vLLM remains the serious multi-GPU experiment path, and direct `llama.cpp` stays in the benchmark/watch lane.
- Updated current-state and software-stack docs so the install-target review is visible outside the sweep output.
- Added a generated wiki layer under `docs/wiki/generated/` with a builder script that turns the fact notebook into browsable markdown: latest briefing, entity pages, source pages, generated log, and generated index.
- Kept the architecture repo-first and automation-first: generated wiki pages are a local view layer for Obsidian, not the source of truth.
- Wired the generated wiki builder into `sweeps/run_workflow.py` so normal scheduled runs refresh the wiki view automatically after notebook ingest, and again after weekly rollup generation.
- Reviewed the 2026-04-16 daily sweep and logged a more specific `llama.cpp` multi-GPU watch signal: CUDA P2P now requires explicit opt-in and NCCL communicator handling is still moving, which reinforces direct `llama.cpp` as benchmark/watch territory rather than a day-one dependency.
- Evaluated Simon Willison's Datasette activity as workflow-interesting rather than node-critical: potentially useful later as a lightweight view layer over notebook data, but not something that should displace the current markdown + SQLite + email loop.
- Logged `Qwen3.5-35B-A3B` as a future vLLM benchmark candidate rather than a day-one target model.
- Reviewed the 2026-04-17 daily sweep and raised the Ollama install-target pressure again: `v0.21.0` now needs review before hardware bring-up.
- Logged `Qwen3.6-35B-A3B` as a more credible future vLLM benchmark candidate after fresh local-use signal, while keeping it out of the day-one model plan.
- Reviewed the 2026-04-18 daily sweep and added `vLLM v0.19.1` to the release-review queue, since the current plan was already pinned to `v0.19.0`.
- Kept recent `llama.cpp` CUDA graph and Gemma4-shape changes in the benchmark/watch lane only; they do not change the day-one serving order.
- Corrected the `Kimi K2.6` framing: open-source model with official local runtime paths worth tracking seriously, but still not practical on the current 3x3090 node, so it remains outside the day-one local-node plan.
- Reviewed the 2026-04-21 daily sweep and logged `llm-openrouter 0.6` as future routing/fallback tooling worth watching.
- Kept the new `llama.cpp` OOM retry and Gemma-4 tensor-parallel fixes in the benchmark/watch lane only; they reinforce that direct `llama.cpp` is still moving too quickly to treat as a stable day-one dependency.
**Commits:** Pending
**Next:** Review `Ollama v0.21.0` and `vLLM v0.19.1` release notes closely enough to decide whether the pinned install targets should move before hardware bring-up.

## 2026-04-12 (Session 4)
**Focus:** Nodehome sweep automation and compounding notebook loop
**What was done:**
- Decision logged: weekly rollup should be generated automatically from the fact notebook, but weekly email stays gated until the rollup proves inbox-worthy.
- Chosen workflow: `daily sweep -> fact notebook -> weekly rollup -> optional weekly send`.
- Weekly generation should run through `sweeps/run_workflow.py --profile all --weekly`.
- Weekly email should require explicit opt-in via `--send-weekly` or `DIGEST_WEEKLY_EMAIL_ENABLED=true`, plus normal Resend email env.
**Commits:** Pending
**Next:** Wire weekly rollup generation into the workflow runner and scheduler docs.

## 2026-04-07 (Session 3)
**Focus:** CPU cooler decision, final component sourcing, Codex build review
**What was done:**
- Researched cooler alternatives after 3mm Arctic Freezer 4U-M clearance concern raised
- Full market sweep: Noctua NH-U9 TR4-SP3 (125mm, 23mm clearance), Supermicro SNK-P0064AP4 (126mm, 22mm), Dynatron A50 (110mm, loud)
- Caught user about to buy wrong cooler (NH-U9S consumer != NH-U9 TR4-SP3 server)
- Noctua TR4-SP3 out of stock at MSRP everywhere. UK seller cheapest at ~$168. Amazon out of stock.
- Supermicro SNK-P0064AP4 available at ~$84 but 38 dBA - loudest component at idle in living room
- Final decision: Noctua from Ada (kuaka02) at $150 ($161.29 incl tax). Near-silent at idle matters for living room placement.
- SilverStone RM400 chassis purchased (Amazon, arriving Sat 2026-04-12)
- SysRacks 24x24 rack purchased ($75), came with Noctua NF-A12x25 PWM case fan
- Mobo+CPU (EPYC 7302P + H12SSL-i v2.0) arrived today ($985.08)
- ALL COMPONENTS NOW PURCHASED - total ~$5,910 incl tax
- MemoryPartner_Deals and quark_12 confirmed same entity (identical messages). Most other GPU sellers said no.
- Codex reviewed full build spec - validated architecture, flagged 120V circuit concern, airflow critique corrected (blower cards are the airflow)
- Updated all docs: cooler change reflected in HANDOVER_ASSEMBLY, HANDOVER_SOURCING, CURRENT_STATE, CLAUDE.md, hardware-spec
- Card retainer bracket can now likely stay with Noctua (5mm clearance vs Arctic's impossible fit)
- Logged `Locker` as a possible file-ingest/file-store layer, but explicitly left open whether to adopt it or build a narrower in-house version
- Added a proposed daily research-sweep architecture: narrow watchlist, daily diffs, digest files, and manual promotion into the `raw/` -> `wiki/` pipeline
- Refined the sweep design into four lanes: AI workflows, local inference infra, hardware optimization, and local AI node scene, with explicit room for early strange high-upside ideas
- Added a concrete starter watchlist for each sweep lane, with primary vs fragile sources and a per-item digest format
- Scaffolded the sweep system: source manifest, no-dependency Python runner, output directories, and local diff state under `docs/sweeps/`
- Reframed the sweep architecture as X-first for discovery, with GitHub/blogs/releases as validation layers; added a starter X account list and manifest placeholders
- Expanded the curated X watchlist with infra, local-node scene, and operator-style accounts: LMSYS, ggerganov, Hugging Face, Qwen, Open WebUI, LM Studio, geerlingguy, and Prince Canuma
- Added `@fchollet` to the workflow lane of the curated X watchlist
- Split the sweep into `core` and `extended` profiles and added concurrent fetches to keep daily runs fast enough
- Separated daily digest output by profile so `core`, `extended`, and `all` runs do not overwrite each other
- Added a Windows Task Scheduler registration script and scheduling docs for daily `core` and `extended` sweep runs
- Added automatic validation-queue generation for new social posts with outbound links, separating discovery from follow-up
- Upgraded validation follow-ups to classify link type/priority and optionally generate raw intake stubs for high-priority items
- Added source retries, cached-state fallback messaging, and per-run health reports so flaky X bridges are visible
- Added rolling degraded-source tracking to support future auto-quarantine of persistently failing feeds
- Added top-signals digest ranking, automatic quarantine for repeatedly degraded sources, and weekly rollup stubs
- Added cooldown-based source recovery so quarantined feeds are retried automatically after a delay
- Improved digest ranking and validation enrichment with resolved follow-up domains and fetched page titles
- Added automated weekly rollup generation from daily digests
- Enriched validation follow-ups further with fetched page descriptions for faster triage
- Logged weekly rollup synthesis via local `Ollama` as a future first-class Sovereign Node task once inference is online
- Added a third wave of curated X sources from the Karpathy-adjacent network: hardmaru, _akhaliq, rasbt, soumithchintala, jeremyphoward, arankomatsuzaki, AIatMeta, and ericjang11
- Elevated Georgi Gerganov, Open WebUI leadership, and the LM Studio team in the docs as first-tier public builders to watch in local-first AI
- Added build-specific sources for local inference and rack homelab relevance: TheBlokeAI, technomancers_ai, concat_ai, ServeTheHome, Level1Techs, and VideoCardz; flagged _akhaliq and arankomatsuzaki as volume-risk sources to review
- Added Resend email-delivery scaffolding: separate sender script, workflow runner, env example, and scheduler flow updated to `generate -> optional send`
- Captured David Mohl's `MCP vs Skills` framing as a useful `connectors vs manuals` pattern for Nodehome and Sovereign Node: MCP/connectors for service access, skills/manuals for gotchas and operator knowledge
**Commits:** N/A
**Next:** Inspect mobo+CPU (socket pins, BMC password). Await remaining deliveries. Assembly when GPUs arrive.

## 2026-04-04 (Session 2 - Continuation)
**Focus:** GPU purchase, RAM purchase, documentation architecture buildout
**What was done:**
- Recovered Karpathy research dossier from compacted transcript (41 tool uses reconstructed)
- Complete eBay market sweep across ALL 3090 blower variants (Gigabyte Turbo, GALAX Turbo, MSI Turbo, ASUS Turbo, WinFast, MSI AERO S)
- Confirmed PNY blower 3090 does not exist, Dell OEM is dual-fan not blower
- Messaged 7 GPU sellers with bulk offer ($2,900-3,000 for 3 cards) - only kuaka02 responded
- kuaka02 (Ada) countered at $3,180 ($1,060/ea shipped FedEx air) - PURCHASED, eBay #227287677142, $3,442.35 incl tax
- RAM sweep: DDR4-2133/2400 kits at $420-550, DDR4-2933 at $700-1000+ (Gemini's $300 claim debunked)
- RAM PURCHASED from scwcomputers at $420 (128GB Samsung HPE DDR4-2133), order #03-14469-02999
- Confirmed mobo+CPU ($910) and PSU ($223) also purchased
- Evaluated Gemini's market analysis multiple times - caught fabricated PNY listing, fake Intel B70 narrative, wildly wrong RAM pricing, fabricated seller details
- Built full MealMastery-style documentation architecture: 26 files across 8 layers
- Expanded wiki to 19 articles (8 concepts, 4 decisions, 6 research, 1 incident)
- 5 of 7 build components purchased, 2 remaining (chassis + cooler) + server rack
**Commits:** N/A (no code yet)
**Next:** Source chassis (~$260), cooler (~$70), server rack (~$75). Await GPU shipment (ETA Apr 16-28). Begin assembly planning.

## 2026-04-03 (Session 1 - Original)
**Focus:** Build spec review, component sourcing, market research
**What was done:**
- Reviewed and corrected Sovereign Node executive summary (FP16 claims, context window claims, solar math)
- Identified blower 3090 as critical path component
- Extensive eBay sourcing: analyzed sellers (MemoryPartner, ea_memory, aymdam-0, squaredseller, e-dealsglobal, long2207)
- Confirmed Alibaba is MORE expensive than eBay for 3090 blowers
- Locked mobo+CPU combo at $910 (tugm4470)
- Locked PSU at $223 (respec.io)
- Purchased SSD (Acer GM7 2TB, $269)
- Deep dive: Shenzhen electronics ecosystem, ITAD supply chain, GPU resale side hustle analysis
- Deep dive: Hyperscaler CapEx ($600B+/yr 2026, $1.3T over 3 years)
- Deep dive: Gemma 4 26B MoE discovery (3.8B active params, single 3090)
- Deep dive: Karpathy X/GitHub research (autoresearch, cognitive core, knowledge base workflow)
**Commits:** N/A
**Next:** GPU offers pending, RAM sourcing
