# Session Scratch - 2026-05-12 (Session 18, afternoon)
Focus: Drive #1 purchase + real-time market-shock confirmation + Drive #2 hunt in progress. Continuation of morning's digest review and sweep pipeline maintenance.

## What was decided/executed this session
- **Drive #1 purchased:** WD My Book 12TB (`WDBBGB0120HBK-Newm`), Walmart, $249. Last 2 in stock at that location. Arrives 2026-05-12 evening.
- **Market shock confirmed industry-wide.** Same SKU spiked to $323.49 hours after purchase. Multi-retailer check confirmed: WD sold out for 2026, prices up ~46% since Sept 2025, Best Buy 12TB Easystore sold out, Newegg $440. Root cause: AI-hyperscaler nearline HDD demand.
- **New durable doc:** `docs/wiki/concepts/hardware-supply-2026.md` capturing the market context, related DDR4 ECC RDIMM trajectory, decision rules for spending in this market.
- **Drive #2 hunt in progress** (no commit yet):
  - YellowChoo 12TB Easystore: opened $150 best offer → seller countered $175 → user re-countered $160 (pending).
  - savsystems 14TB Elements "for parts": $30 best offer sent (technical-buyer side bet, recoverable-drive odds ~60-65%).
  - Reviewed and passed on two used 14TB drives with concerning SMART data (34-36k power-on hours, 30,710 Read Recovery Attempts on one of them).
- **Drive placement decision:** existing 1U cantilever shelf at U7 above the RM400. No purchase needed. Drives side-by-side, USB cables with slack loop for slide-out.

## Open follow-ons
- Tonight: receive Drive #1, run on-arrival checklist (lsblk, dmesg, smartctl `-d sat`, wipefs, mkfs.ext4, fstab with `nofail`+`noatime`, dd burn-in, optional smartctl long test overnight). Mount at `/mnt/storage`.
- Wait 24-48h on YellowChoo $160 counter.
- Wait on savsystems $30 response.
- If YellowChoo declines or holds firm at $175: meet at $175 ($195 total) — still a good deal in this market, 30-day returns is the safety net.
- If YellowChoo deal falls through entirely: "I Sell Hard Drives" 14TB Easystore at $196 ($206.70 total, no returns but HDD specialist with strong DOA-handling track record) is the strongest backup.
- After both drives in: spin up Jellyfin container, ingest first household media test content.

## Budget state
- Spent: $249 (Drive #1)
- Remaining: $251 of $500
- Expected Drive #2 landing: $180-195 → total $429-444 (under budget by $56-71)
- Worst-case Drive #2 (full retail backup play): $250 → total $499 (right at ceiling)
- savsystems experiment: $30 separate, not budget-counted

## Carried forward from this morning (Session 18 core)
- Sweep pipeline bugs (4 open, see `sweeps/PIPELINE_FOLLOWUPS.md`): vLLM title-swallow [recurring], synthesis boilerplate, consumer-gaming mis-classification, GitHub activity duplicates, partial-keyword mis-tags.
- vLLM blog signal recovered: TurboQuant KV-cache quantization post worth reading when convenient (directly applies to the `--gpu-memory-utilization 0.85` production posture).
- Ollama v0.30.0-rc15 + v0.23.3 stable both shipped; deferred to next monthly upgrade review per `docs/runbooks/upgrade-cadence.md`.
- Open WebUI rolling-tag `:main` should re-pull as `:v0.9.5` explicit pin per the same upgrade-cadence doc.

## Carried forward from earlier sessions (Sessions 16-17, still relevant)
- Permanent in-chassis install complete; rack-installed on Tedgetal sliding shelf at U3-U6.
- All 3 GPUs at PCIe Gen 4 x16 under load; pigtail rule still enforced on GPU 2 via Ollama `CUDA_VISIBLE_DEVICES=0,1` until GPU 3 cable arrives (window 2026-05-23 to 2026-06-10).
- BMC fan threshold fix landed (`docs/runbooks/bmc-fan-thresholds.md`).
- Option C resolved (Open WebUI routes to both Ollama and vLLM; per-model system prompt grounds Qwen in local hardware).
- Home media server scope captured (`docs/runbooks/home-media-server.md`).
- IPMI hardening scope captured (`docs/runbooks/ipmi-hardening.md`) — 4 phases, 4 decisions blocking execution.
- Stack upgrade cadence policy captured (`docs/runbooks/upgrade-cadence.md`).
- Local-AI thesis external references (`docs/wiki/research/local-ai-thesis-external-references.md`).
- Hardware supply 2026 context (`docs/wiki/concepts/hardware-supply-2026.md`) — new this session.

## Operational lessons added this session
- **Tech prices are climbing in 2026, not falling.** Specifically: HDDs (AI-hyperscaler demand) and DDR4 ECC RDIMM (EOL). The "buy when needed" framing only safely applies if (a) the use case is concrete and (b) the category isn't in supply distress. For HDD/DDR4 ECC RDIMM with a real use case, prefer buy-now over wait-and-see.
- **Used 14TB market is now dominated by heavy-use datacenter pulls.** Watch SMART data carefully — Read Recovery Attempts is the leading indicator of failure on rotating media, more telling than reallocated sector count alone (because retries hide trouble until they stop working). 30k+ Read Recovery Attempts is a pass regardless of how clean the other counters look.
- **Real-time price spikes confirm supply distress, not just listing variance.** Same SKU jumping 30% intraday on the last in-stock unit is a market signal, not an outlier.
