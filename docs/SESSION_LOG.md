# Sovereign Node - Session Log
<!-- At the start of each month, move previous month's entries to docs/archives/SESSION_LOG_YYYY-MM.md -->

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
- Caught user about to buy wrong cooler (NH-U9S consumer ≠ NH-U9 TR4-SP3 server)
- Noctua TR4-SP3 out of stock at MSRP everywhere. UK seller cheapest at ~$168. Amazon out of stock.
- Supermicro SNK-P0064AP4 available at ~$84 but 38 dBA — loudest component at idle in living room
- Final decision: Noctua from Ada (kuaka02) at $150 ($161.29 incl tax). Near-silent at idle matters for living room placement.
- SilverStone RM400 chassis purchased (Amazon, arriving Sat 2026-04-12)
- SysRacks 24x24 rack purchased ($75), came with Noctua NF-A12x25 PWM case fan
- Mobo+CPU (EPYC 7302P + H12SSL-i v2.0) arrived today ($985.08)
- ALL COMPONENTS NOW PURCHASED — total ~$5,910 incl tax
- MemoryPartner_Deals and quark_12 confirmed same entity (identical messages). Most other GPU sellers said no.
- Codex reviewed full build spec — validated architecture, flagged 120V circuit concern, airflow critique corrected (blower cards are the airflow)
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
