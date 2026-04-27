# Daily Research Sweeps

**Date:** 2026-04-10
**Status:** Operational

## Goal

Build a daily internet sweep that catches high-signal changes in local AI, agent tooling, and Karpathy-adjacent workflows without requiring constant manual monitoring.

This is not a general news feed. It should answer:

- What changed since yesterday?
- What is worth reading in full?
- What should enter the `raw/` -> `wiki/` pipeline?
- What affects Sovereign Node directly?
- What new ideas are early, strange, or underexplored but worth tracking?

## Core Orientation

This is a `fact accumulation system`: source feeds are inputs, the notebook is the product, and the digest/email are views into that notebook.

For the lanes we care about — AI workflows, local-node infra, hardware, and the builder scene — the first appearance of an idea is often on X. X posts, replies, quote posts, screenshots, and offhand comments are primary ideation artifacts, not replaceable by blogs/GitHub/Bluesky. The operational problem is that free X access is unreliable, not that X is unimportant.

The intended stack is:

- `X` = primary ideation layer when available (posts, replies, quote context, early vocabulary)
- `X email notifications` = automated low-risk capture path for selected X notifications
- `blogs/RSS/YouTube` = durable artifact layer (long-form writeups and official announcements)
- `Bluesky` = parallel public social signal for accounts that cross-post there
- `GitHub` = code / implementation validation layer
- `SQLite fact notebook` = durable memory layer
- `wiki` = curated synthesis / article layer

Durable feeds and Bluesky are redundancy layers, not substitutes for X. When X is dark, they keep the system from going blind. When X works, it remains the best source for early thought and social context.

## Design Principles

- Prefer primary sources over commentary.
- Track diffs, not just headlines.
- Treat X as primary ideation but operationally fragile.
- Produce a short operator digest, not an unread pile of links.
- Accumulate durable facts even when an item is not promoted into a full wiki note.
- Separate "what the field is converging on" from "what might become important early."
- Design for bounded local-model context: extract small facts, reset context, persist memory outside the model.

## Output Shape

Each daily run should produce one digest with:

- 5-15 notable changes
- 1-line why-it-matters for each
- source link
- confidence label: `primary`, `secondary`, or `fragile`
- action label: `ignore`, `watch`, `read`, `promote`
- novelty label: `established`, `emerging`, or `speculative-interesting`

Optional weekly rollup:

- biggest themes
- repeated patterns
- new tools worth testing
- decisions that may need revisiting

## Source Tiers

### Tier 1: Primary Sources

These should be the backbone of the system.

- Andrej Karpathy blog: `https://karpathy.github.io/`
- Andrej Karpathy GitHub activity and repos: `https://github.com/karpathy`
- Simon Willison main Atom feed: `https://simonwillison.net/atom/everything/`
- vLLM blog: `https://blog.vllm.ai/`
- vLLM GitHub releases / changelog: `https://github.com/vllm-project/vllm`
- Ollama blog / changelog: `https://ollama.com/blog`
- Ollama GitHub repo: `https://github.com/ollama/ollama`
- llama.cpp repo / releases: `https://github.com/ggml-org/llama.cpp`
- Hugging Face blog for open-model announcements: `https://huggingface.co/blog`

### Tier 2: Targeted People / Labs

Useful, but should not dominate the digest.

- Karpathy social posts for early signals
- Simon Willison linkblog and social posts
- Major open-model labs only if directly relevant to local inference or agent workflows

Examples:

- Meta Llama announcements
- Google Gemma announcements
- Qwen announcements

### Tier 2.5: Durable Fallbacks for X-Heavy Sources

These feeds cover the same people/orgs tracked via X, but through their blog, newsletter, or YouTube channel. They produce the long-form artifacts that X posts often point to. When X is dark, these keep coverage alive.

| Source | Feed | Lane | Covers |
|--------|------|------|--------|
| Sebastian Raschka | `magazine.sebastianraschka.com/feed` | workflow | Ahead of AI newsletter — LLM architecture, coding agents, attention variants |
| fast.ai | `www.fast.ai/index.xml` | workflow | Jeremy Howard + Rachel Thomas — AI education, practical deep learning |
| Answer.AI | `www.answer.ai/index.xml` | workflow | Jeremy Howard's research lab — applied AI R&D, tool use, agents |
| Jeff Geerling | `www.jeffgeerling.com/blog.xml` | hardware | Homelab builds, SBCs, Linux hardware, DRAM/storage market |
| Jeff Geerling | YouTube (`UCR-DXc1voovS8nhAvccRZhg`) | hardware | Same coverage as blog, video format |
| ServeTheHome | `www.servethehome.com/feed/` | hardware | Enterprise/server hardware reviews, AI server builds, cooling |
| ServeTheHome | YouTube (`UCv6J_jJa8GJqFwQNgNrMuww`) | hardware | Same coverage as blog, video format |
| Level1Techs | YouTube (`UC4w1YQAJMWOz4qtxinq55LQ`) | hardware | Wendell's GPU/server/homelab content, multi-GPU builds |

These are `confidence: primary` — first-party feeds with reliable uptime. They should never be the only source for a person (X still catches fast-moving chatter), but they guarantee baseline coverage.

### Tier 3: Fragile / Social Sources

These are valuable for early discovery but operationally unreliable.

- X accounts via OpenRSS (intermittent availability, service-level outages)
- conference talk clips
- random blogs surfaced by link-chasing

Use these for discovery bonus yield, not as the foundation. Every high-value Tier 3 source should eventually get a Tier 2.5 durable fallback where one exists.

## Sweep Lanes

Run the sweep as multiple lanes, not one blended feed.

### 1. AI Workflows

Track:

- Karpathy-style loops and personal AI workflows
- agentic engineering patterns
- eval habits
- note-taking / knowledge-base workflows
- human-in-the-loop patterns that actually work

Question this lane answers:

- "What are the best new ways to think and work with AI day to day?"

### 2. Local Node / Inference Infra

Track:

- Ollama
- vLLM
- llama.cpp
- quantization and multi-GPU serving
- context and memory handling
- orchestration and self-hosted interfaces

Question this lane answers:

- "What can our node do better now than it could last month?"

### 3. Hardware Optimization

Track:

- RTX 3090 tuning and thermals
- NVIDIA driver changes
- idle power and power limiting
- PCIe quirks
- rack airflow and cooling patterns
- used GPU market shifts
- upgrade-path economics

Question this lane answers:

- "How do we run this physical build harder, cooler, quieter, and cheaper?"

### 4. Local AI Node Scene

Track both:

- convergence: what serious local-first builders are repeatedly choosing
- discovery: fresh, weird, early ideas that may become important later

Examples:

- home GPU clusters
- private RAG appliances
- local coding-agent stacks
- personal AI servers
- unusual but promising storage / ingest / orchestration patterns

Question this lane answers:

- "What are people like us building, and what new ideas are emerging before they become standard?"

## Recommended Initial Watchlist

Start narrow. Too many feeds will bury the signal.

### People

- Andrej Karpathy
- Simon Willison
- a small set of local-first builders added over time based on repeated signal, not popularity

### Infra / Serving

- vLLM
- Ollama
- llama.cpp

### Model Ecosystem

- Hugging Face blog
- Meta Llama announcements
- Google Gemma announcements
- Qwen announcements

### Repos Worth Watching

- `karpathy/autoresearch`
- `karpathy/nanochat`
- `vllm-project/vllm`
- `ollama/ollama`
- `ggml-org/llama.cpp`

### Scene / Discovery Sources

Use sparingly and expand only after the MVP proves useful:

- selected GitHub repos discovered via repeated citation
- narrowly chosen X accounts
- high-signal blogs from builders running local clusters or personal AI systems
- occasional forum / Reddit / Hacker News discovery only when it leads to primary-source follow-up

## Starter Watchlist

This is the first concrete set to automate against.

### Lane 1: AI Workflows

Primary:

- Andrej Karpathy blog: `https://karpathy.github.io/`
- Andrej Karpathy GitHub: `https://github.com/karpathy`
- Simon Willison Atom feed: `https://simonwillison.net/atom/everything/`
- Simon Willison GitHub: `https://github.com/simonw`

Fragile but high-value:

- `@karpathy` on X for early workflow ideas and naming shifts
- Simon Willison social posts for early tool observations

Why these:

- Karpathy is still one of the highest-signal sources for workflow framing, personal AI loops, and early vocabulary that later propagates outward.
- Simon Willison is consistently strong on practical LLM workflows, tool usage, local experimentation, and link curation.

### Lane 2: Local Node / Inference Infra

Primary:

- vLLM blog: `https://blog.vllm.ai/`
- vLLM releases: `https://github.com/vllm-project/vllm/releases`
- Ollama blog: `https://ollama.com/blog`
- Ollama repo: `https://github.com/ollama/ollama`
- llama.cpp releases: `https://github.com/ggml-org/llama.cpp/releases`
- llama.cpp repo: `https://github.com/ggml-org/llama.cpp`

Why these:

- This lane should track direct changes to self-hosted inference capabilities, API compatibility, performance tuning, and multi-model serving.
- vLLM, Ollama, and llama.cpp are close to the center of the local-node tool surface.

### Lane 3: Hardware Optimization

Primary:

- llama.cpp releases: `https://github.com/ggml-org/llama.cpp/releases`
- vLLM blog: `https://blog.vllm.ai/`
- vLLM releases: `https://github.com/vllm-project/vllm/releases`

Secondary:

- selected NVIDIA developer forum threads only when they are directly relevant to RTX 3090 Linux behavior
- Puget Systems and similarly measurement-heavy tuning writeups when they provide actual data

Fragile:

- builder reports from Reddit / forums on 3090 thermals, power limits, rack airflow, or PCIe issues

Why these:

- Most good hardware signal shows up indirectly through release notes, performance deep dives, bug reports, and measured tuning posts, not through glossy hardware news.

### Lane 4: Local AI Node Scene

Primary:

- Hugging Face blog: `https://huggingface.co/blog`
- Ollama blog: `https://ollama.com/blog`
- Simon Willison Atom feed: `https://simonwillison.net/atom/everything/`

Secondary:

- GitHub repos that repeatedly show up in local-first workflows
- posts from builders shipping personal AI servers, local agent stacks, or private RAG systems

Fragile but useful:

- narrowly selected X accounts
- Hacker News threads only when they link to primary build writeups or repos
- Reddit threads only when they reveal real operator patterns, not just hype

Why these:

- This lane is part convergence map and part idea radar.
- We want both what competent operators are repeatedly choosing and what weird new patterns might matter before they become normal.

## Immediate Adds After MVP

If the first month produces usable signal, add:

- Meta Llama announcement sources
- Google Gemma announcement sources
- Qwen official announcements
- a small curated list of local-first builders discovered through repeated citations

Do not add these on day 1 unless they are already creating clear signal.

## Sweep Pipeline

### Daily

1. Fetch subscribed feeds, release pages, and repo activity.
2. Compare against the previous snapshot.
3. Extract only new or changed items.
4. Score items by relevance to:
   - local inference
   - agent workflows
   - knowledge-base workflows
   - model-serving performance
   - Karpathy-style research loops
   - scene convergence
   - scene discovery / novelty
5. Generate a concise markdown digest.
6. Promote top items into `docs/wiki/raw/` only when they justify deeper synthesis.

### Weekly

1. Review the last 7 daily digests.
2. Group repeated themes.
3. Create one weekly synthesis note.
4. Flag any architecture or tool decisions that may need revision.

## Storage Pattern

Suggested structure:

- `docs/sweeps/daily/YYYY-MM-DD.md`
- `docs/sweeps/weekly/YYYY-WW.md`
- `docs/wiki/raw/` for promoted source captures

Only promoted items should enter the wiki pipeline.

## Daily Deliverable Format

Each digest should group items by lane:

- `workflow`
- `infra`
- `hardware`
- `scene`

Each item should include:

- title
- source
- date seen
- why it matters
- confidence
- novelty
- action

This keeps the digest readable and makes it obvious whether a day produced:

- a practical workflow pattern
- an infra upgrade signal
- a hardware tuning lead
- an early weird idea worth watching

## Triage Rules

Promote an item if it:

- introduces a new workflow pattern
- changes the feasibility of local inference
- affects our planned software stack
- provides an unusually clear explanation of an emerging idea
- keeps recurring across multiple trusted sources
- is novel enough to potentially reshape how we build or use the node

Do not promote an item if it is:

- hype without implementation details
- a repost of an older idea
- model leaderboard noise with no operational consequence
- commentary on commentary

Keep lane-specific judgment:

- `workflow`: reward repeatable patterns
- `infra`: reward operational impact
- `hardware`: reward measured tuning data and failure reports
- `scene`: reward either repeated adoption or unusually strong early ideas

## X / Social Strategy

X is primary ideation, not guaranteed transport.

**Why X transport is unreliable:** OpenRSS is a fragile free X-to-RSS bridge. Nitter instances are dead, RSSHub removed its Twitter route, and RSS Bridge returns 500s. OpenRSS itself has intermittent outages and per-account scraping failures. Even with throttling, success rate for 27 X feeds can range from partial coverage to full outage.

**Operational model:**

- Treat X-originated posts, replies, quote context, screenshots, and offhand comments as primary source material when captured
- Use official X API only if a safe token/cost posture exists
- Use X email notifications as the current automated, low-risk capture path
- Keep OpenRSS as the automatic fallback when no `X_BEARER_TOKEN` is present, or force it explicitly with `SWEEP_OPENRSS_FALLBACK_ENABLED=true`
- Use `SWEEP_OPENRSS_FALLBACK_ENABLED=false` only if you want to suppress OpenRSS entirely and accept degraded X coverage
- Add durable fallbacks (blog, YouTube, GitHub, Bluesky) for baseline continuity, not as replacements
- The quarantine system handles persistent failures automatically (3 consecutive failures = 12h cooldown)

**What X is still good for:**

- first sightings and vocabulary shifts
- workflow memes that may become real patterns
- operator reports and early architecture sketches
- replies, quote-posts, and comments where half-formed ideas develop
- cross-pollination between builders who don't read each other's blogs

**Working model:**

- `X email notifications` catch selected X-originated posts automatically
- `OpenRSS` catches additional X chatter only when explicitly enabled and available
- `blogs/YouTube/RSS` catch durable artifacts
- `Bluesky` catches public social cross-posts where accounts participate
- `GitHub` shows whether an idea is becoming code
- `SQLite fact notebook` records durable claims and reinforcement over time
- `wiki` records curated synthesis and article-ready material

## Fact Notebook Architecture

The sweep should evolve from a feed reader into a fact accumulation engine.

Current flow:

1. Fetch sources.
2. Render daily digest.
3. Email the digest.
4. Parse the digest into facts.
5. Store facts in `docs/sweeps/notebook/facts.sqlite` with SQLite WAL.

Target flow:

1. Fetch source items.
2. Extract atomic facts from each item.
3. Store facts with source URL, source name, published date, lane, topic, confidence, first seen, last seen, and seen count.
4. Detect reinforcement, gaps, and contradictions from the fact store.
5. Generate daily digest, weekly rollup, and article candidates as views over the notebook.

The notebook is the durable product. The digest and email are presentation layers.

Local-model implication:

- Do not rely on huge context windows.
- Process one item or small batches at a time.
- Extract compact structured facts.
- Reset context between extraction passes.
- Merge and dedupe outside the model in SQLite.

This follows the Ralph Loop / laconic lesson from Steve Hanov: treat the context window as disposable and keep memory in the filesystem/database.

## Guardrails

Based on the existing `ai-agent-traps` work:

- never trust summary-only ingestion
- store source URL and capture date on every promoted item
- require source verification before a sweep item becomes a decision
- keep agent-generated labels separate from raw source text

## Recommended MVP

Do this first:

- RSS / Atom polling
- GitHub repo release + commit monitoring
- markdown digest generation
- manual promotion into `docs/wiki/raw/`

Do later:

- X account monitoring
- automatic raw-note generation
- automatic Obsidian note linking
- semantic clustering and trend detection

## Current Recommendation

Build a narrow internal sweep system instead of trying to buy a giant research-monitoring tool.

Phase 1 should be boring and reliable:

- four explicit lanes
- a small watchlist per lane
- daily diffing
- one digest file with lane tags
- one promotion path into the wiki

If this works for a month, then expand the source set and add limited social scraping.

## Current Scaffold

Initial local scaffold added:

- source manifest: `sweeps/sources.json`
- runner: `sweeps/run_daily.py`
- outputs: `docs/sweeps/daily/`
- weekly rollups: `docs/sweeps/weekly/`
- diff state: `docs/sweeps/state/`

This is deliberately MVP-level:

- feed-first
- no external dependencies
- markdown output
- simple page hashing fallback for sources without feeds
- concurrent fetches with OpenRSS throttling (semaphore, max 2 concurrent, 2-5s stagger delay)
- XML sanitizer for feeds with invalid bytes (e.g. terminal control characters in Answer.AI feed)
- profile split: `core` vs `extended`
- durable fallback feeds for X-heavy extended sources (blogs, YouTube, newsletters)

This means the current code scaffold is still behind the intended design.

The intended end state is:

- `X-first` discovery input
- validation feeds and repos behind it
- one daily digest that mixes fresh discovery with confirmed follow-up
- separate validation queue for social items with outbound links
- typed follow-up targets with optional raw-intake stub generation for high-priority items
- enriched follow-up metadata so validation is closer to a real triage queue than a raw link dump
- short fetched follow-up summaries to reduce click-through during validation review
- source health tracking so discovery outages are visible instead of silently looking like a quiet day
- rolling degradation tracking so persistently bad sources can be quarantined later if needed
- quarantine is temporary: degraded sources re-enter after a cooldown so recovery is automatic
- top-signals section to reduce scan time on each daily digest
- weekly rollup stubs so synthesis has a fixed landing zone from day one
- automated weekly rollup generation from accumulated daily digests
- once the local inference server is running, weekly rollups are a natural first "Sovereign Node does real work" task: have `Ollama` synthesize the week's digests into the rollup instead of relying only on Python heuristics
- optional daily email delivery via Resend as a separate post-generation step

## Operating Mode

Run this in two profiles:

- `core`: high-signal daily must-watch sources
- `extended`: broader scene and secondary sources

Recommended rhythm:

- run `core` every day
- run `extended` separately when you want wider coverage
- use `all` only for a full sweep or debugging

Suggested output pattern:

- `core` digest: `docs/sweeps/daily/YYYY-MM-DD.md`
- `extended` digest: `docs/sweeps/daily/YYYY-MM-DD.extended.md`
- `all` digest: `docs/sweeps/daily/YYYY-MM-DD.all.md`
- validation queue mirrors this under `docs/sweeps/validation/`

## Future Upgrade Path

When the local inference server is online, the weekly rollup is a strong first production task for Sovereign Node itself.

Why this fits:

- the inputs are already local markdown files
- the task is bounded and repeatable
- the output benefits from synthesis rather than simple extraction
- it closes the loop between the research sweep system and the inference stack

Recommended evolution:

- keep the current Python weekly builder as the baseline/fallback
- add an `Ollama`-backed synthesis step that reads the week's daily digests
- let the model produce the human-readable weekly rollup
- keep deterministic metadata generation in Python around it

This is a good first example of "Sovereign Node does real work" rather than just hosting models.

## Starter X Account List

Small, curated, and role-based.

### Workflow / Idea Sources

- `@karpathy`
- `@simonw`
- `@fchollet`

### Infra / Serving Sources

- `@vllm_project`
- `@ollama`
- `@lmsysorg`
- `@ggerganov`
- Open WebUI leadership / project signals
- LM Studio team / project signals

### Scene / Discovery Sources

Start very small and expand only after repeated signal:

- builders repeatedly cited by Karpathy, Simon, or local-node tooling discussions
- teams publishing real local-agent or personal-AI-system experiments

Current second-wave additions:

- `@huggingface`
- `@Alibaba_Qwen`
- `@OpenWebUI`
- `@lmstudio`
- `@geerlingguy`
- `@Prince_Canuma`

Current third-wave additions from the Karpathy-adjacent network:

- `@hardmaru`
- `@_akhaliq`
- `@rasbt`
- `@soumithchintala`
- `@jeremyphoward`
- `@arankomatsuzaki`
- `@AIatMeta`
- `@ericjang11`

Build-specific additions for the Sovereign Node / rack homelab lane:

- `@TheBlokeAI`
- `@technomancers_ai`
- `@concat_ai`
- `@ServeTheHome`
- `@Level1Techs`
- `@VideoCardz`

Do not start by following dozens of generic AI accounts.

## Critical Public Builders Still Worth Explicit Attention

These are important enough to treat as first-tier figures or projects in the local-first AI stack:

- **Georgi Gerganov / `llama.cpp`**
  Foundational local inference builder. Important not just as a feed source, but as a core reference point for what local-first inference looks like in practice.
- **Tim J. Baek / Open WebUI**
  Strong signal for self-hosted local AI UX, orchestration, and what practical local AI stacks look like for real users.
- **LM Studio team**
  Important for local AI ergonomics, packaging, developer experience, and desktop-local workflows.

These are not just "interesting accounts"; they map directly to the kinds of systems Sovereign Node may either use, compete with, or learn from.

## Watchlist Risks

Some sources may be valuable but still require observation because they can dominate a digest through sheer posting volume.

Current volume-risk sources:

- `@_akhaliq`
- `@arankomatsuzaki`

These should be reviewed after a few days of real runs to see whether they add signal or just flood `extended`.

## X-First Triage

When an item originates on X, classify it as one of:

- `social-primary`: the post itself is the source artifact
- `social-claim`: interesting claim that needs validation
- `social-pointer`: useful link-out to a repo, blog, or benchmark

Promotion rules:

- `social-primary` can enter `raw/` directly if it is intrinsically valuable
- `social-claim` should not become a decision without validation
- `social-pointer` should usually be promoted only after following the linked source
