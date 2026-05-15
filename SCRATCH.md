# Session Scratch - 2026-05-14 (Session 21, evening)
Focus: Storage procurement recovery after Walmart canceled Drive #1; replacement 12TB Easystore secured through eBay within the same market window.

## What was decided/executed this session
- **Walmart Drive #1 canceled:** order `2000146-01251834`, WD My Book 12TB (`WDBBGB0120HBK-Newm`), was canceled as out of stock after support had previously said the order would remain active and be fulfilled. Walmart email says temporary hold on VISA ending `3415` for `$269.54` should release within 10 business days.
- **Replacement Drive #1 secured:** WD Easystore 12TB (`WDBAMA0120HBK`) from eBay seller `sv2deals` (`499`, `100%` positive). Seller declined `$200` and `$210`; accepted `$220` best offer. Listed shipping was `$13.16`; final tax/all-in amount should be verified from order details once payment finishes processing.
- **Replacement SMART evidence is strong:** listing screenshot showed `WDC WD120EDAZ-11F3RA0`, serial `5PJHV96C`, 12 TB, USB, temp `29 C`, uptime `2 days, 6 hours`, `54` power-on hours, `15` power cycles, and zero reallocated / pending / uncorrectable / UDMA CRC errors. Treat as near-new usage but still used/no-retail-warranty until arrival verifies the same serial and SMART data.
- **PayMore Drive #2 still in flight:** WD My Book 12TB "new" from PayMore Westport (seller LLC: SPEEKS Technology, Overland Park KS), eBay order `03-14645-30973`, `$259.79` total with free shipping, delivery May 16-20 via USPS Ground.
- **AI History tool grounding generalized:** first Open WebUI tool test succeeded, but Qwen treated `GPU2` versus physical `GPU #3` as uncertainty. Updated the repo-owned Open WebUI tool to return a reusable `PROJECT_CONTEXT_CONTRACT` with evidence/provenance rules and canonical Nodehome aliases, rather than a one-off GPU2 note.
- **Market shock confirmed industry-wide.** Same SKU spiked to $323.49 hours after purchase. Multi-retailer check confirmed: WD sold out for 2026, prices up ~46% since Sept 2025, Best Buy 12TB Easystore sold out, Newegg $440. Root cause: AI-hyperscaler nearline HDD demand.
- **New durable doc:** `docs/wiki/concepts/hardware-supply-2026.md` capturing the market context, related DDR4 ECC RDIMM trajectory, decision rules for spending in this market.
- **Drive placement decision:** existing 1U cantilever shelf at U7 above the RM400. No purchase needed. Drives side-by-side, USB cables with slack loop for slide-out.

## Validation backlog (re-ranked 2026-05-13 with safety edges tightened)
1. **Staged 2-GPU vLLM thermal soak** — 2026-05-14 status: complete/pass. No-top-fan stock-power run completed 180 iterations with GPU0 topping at `84 C` / `90% fan`; top-fan stock-power repeat completed 180 iterations with GPU0 at `77 C` / `82% fan`, GPU1 at `71 C` / `72% fan`, GPU2 isolated at `1 MiB` / `0% util`, and post-run healthcheck `[HEALTHY] no failures, no warnings`. `350 W + top fan` request baseline averaged about `4.96 s/request`; `300 W + top fan` averaged about `5.16 s/request` (~4% slower). The `300 W + top fan` 180-iteration soak completed cleanly with final loaded state GPU0 `76 C` / `78% fan` / `299 W`, GPU1 `70 C` / `69% fan` / `290 W`, GPU2 idle at `52 C` / `1 MiB` / `0% util` / `P8`, cooldown to `45 C` / `40 C` / `41 C`, and healthcheck `[HEALTHY] no failures, no warnings`. **Production 2-GPU vLLM default: top fan on, GPU0/GPU1 capped at `300 W`, GPU2 unused until the proper SF-1600F14HT cable arrives.** Follow-up: install a narrow persistent power-cap systemd unit only after explicit approval.
2. **Power consumption baseline** — Kill-A-Watt or smart plug. Capture multiple states: idle / vLLM loaded idle / 2-GPU inference under load / (later, post-cable) 3-GPU under load. Foundational data — informs UPS sizing (Tier 1 spend), circuit capacity, heat, noise. Higher-priority than I initially listed.
3. **Healthcheck automation** — **narrow** NOPASSWD entries only for specific read-only commands the script needs (not broad `sudo -n` access). Cleaner alternative: run as root via systemd timer instead of cron. Operational hygiene without broadening the attack surface.
4. **Network throughput** — 2026-05-14 practical SCP baseline complete. `iperf3` installed on `homelab` and server started, but Windows client had no local `iperf3`, so the measured baseline used OpenSSH/SCP over the same 1GbE path. Results: node -> Windows `88.5 MB/s` (~708 Mbps), Windows -> node `67.8 MB/s` (~542 Mbps) using a 1 GiB `/tmp/nettest.bin`; local and remote test files were cleaned up. Interpretation: path is functional but this is an encrypted file-copy baseline, not a clean NIC line-rate test. True `iperf3` remains optional if a Windows client binary is installed later.
5. **Release-notes review** (vLLM v0.21.x, Ollama v0.30.x) — **review BEFORE upgrading, not before proving current stack.** Current stable stack already works; release notes are upgrade-decision input, not validation work.
6. **RAM stress test** — lower urgency since the machine has booted and run on the RDIMMs already. If doing it: `stress-ng --vm 14 --vm-bytes 6G --timeout 4h` style — leave OS headroom (~30-40 GB), don't allocate the full 128 GB.
7. **NVMe non-destructive `fio` benchmark** — **CRITICAL: use `--filename=/path/to/testfile` against a file on the mounted filesystem, NOT raw `/dev/nvme0n1`.** Raw-device fio destroys the filesystem. Test file should be ~10-50 GB on root, removed after.
8. **Multi-model concurrent load** — lower value. Already know vLLM at 0.85 leaves ~2 GiB free, Ollama models won't fit. Test should validate **graceful failure** (Ollama returns OOM cleanly, doesn't crash the host or Open WebUI), not performance.
9. **Backup pipeline groundwork** — wait until external drives are physically present, unless just drafting scripts. Premature setup against non-existent mount points adds zero value.

**Gated on GPU 3 cable arrival** (sustained 3-GPU work, TP=3 vLLM, 70B AWQ across all 3, ReBAR A/B): wait for cable; window 2026-05-23 to 2026-06-10.

## Future hardware spend roadmap
- Captured in `docs/runbooks/hardware-upgrade-roadmap.md` — prioritized future hardware spends with concrete triggers.
- Top of the queue (Tier 1, when next budget available): UPS upgrade (used SMT2200, ~$200-350) + GPU 3 cable backup (~$50-100). ~$250-450 spend covers both.
- Tier 2 (defensive against market trajectory): more RAM (4× 32GB DDR4-2400 ECC RDIMM, ~$320-600). Speculative without workload trigger but DDR4 EOL is climbing.
- Tier 3 (IPMI hardening enabler): managed switch + optional firewall (~$35-300). Only when ready to execute IPMI Phase 2/3.
- Tier 4 (deferred until specific trigger fires): storage expansion, NVMe expansion via Hyper M.2 card, 10GbE networking, PiKVM v4, internal CA.

## Open follow-ons
- **AI history KB long-termization:** repo utility `scripts/ai_history_kb.py` now owns the unified Claude/Codex/Claude Code history resource flow; runbook is `docs/runbooks/ai-history-knowledge-base.md`. First unified DB on node is `~/node-private/chat-exports/unified/index/ai-history-2026-05-14.sqlite` with 210,064 indexed items. Next integration step is Open WebUI tool/function wiring to the local HTTP API, not treating the DB as always-on model memory.
- **Replacement Drive #1 arrival protocol:** on the sv2deals Easystore, first confirm serial `5PJHV96C`, then run `smartctl -d sat -a /dev/sdX` before formatting. Accept only if the SMART story still matches the screenshot: roughly `54` hours, `15` power cycles, and zero reallocated / pending / uncorrectable / CRC errors. If clean: wipefs + ext4 + mount as one of the media drives.
- **Drive #2 arrival protocol:** PayMore WD My Book 12TB is still treated as "new sealed but grey-market/no MFG warranty." Photograph packaging seals before opening; plug in, run `smartctl -d sat -a /dev/sdX` BEFORE formatting; check Power-On Hours (<30 = genuinely new, >200 = wiped-used, file return). If clean: wipefs + ext4 + mount next to Drive #1.
- **SCW RAM return shipped 2026-05-13** (dropped off today). Tracking via eBay return label; awaiting carrier confirmation, then SCW receipt, then $454.65 refund processing (typically 2-5 business days after receipt).
- YellowChoo path dropped (declined $160 / expired; drive showed visible cosmetic damage scratches + chipped enclosure + no SMART data — backed out for cause).
- savsystems $30 parts-drive offer: still pending response, can let it ride.
- After both real drives in: spin up Jellyfin container, ingest first household media test content.
- **Open decision still on the docket: leave factual negative seller feedback for SCW.** Window closes ~2026-06-03 (60 days from 2026-04-04 purchase). Decision deferred — undecided. If yes, factual not emotional. Come back after refund clears.
- **Second rack fan research — circle back after TP=3 thermal data lands.** Researched 2026-05-14 during 300W soak. Existing top fan is AC-powered (wall-wart → DC → fan), plugs directly into rack PDU. **Recommended spec: AC Infinity MULTIFAN S5 (~$25)** — single 120mm + included AC adapter + 3-speed inline controller, designed for AV cabinet exhaust, matches existing fan's plug-and-play AC-PDU pattern. Avoid the chassis-fan path (be quiet! Silent Wings Pro 4 BL098 or Noctua NF-A12x25) — both are 4-pin PWM 12V DC and would require retrofit power delivery for our setup. **Pre-buy task:** identify existing top fan brand/model (photo of fan + wall wart label) — if it's already AC Infinity, just clone it. **Trigger to act:** GPU 0 plateau > 80°C during TP=3 sustained load. If TP=3 stays ≤ 80°C with current setup, no second fan needed.

## Budget state (updated 2026-05-14)
- Walmart WD My Book 12TB: canceled; `$269.54` temporary hold to release, net `$0` once settled.
- Replacement Drive #1 (sv2deals WD Easystore 12TB): `$220` accepted offer + `$13.16` listed shipping; final tax/all-in amount pending order details.
- Drive #2 (PayMore via eBay WD My Book 12TB): `$259.79` (with tax, free shipping).
- **Known subtotal before sv2deals tax: `$492.95`** (`$259.79 + $220 + $13.16`). Likely near or slightly above the original `$500` ceiling after tax, but still defensible in the current 12TB market given one unit is near-new SMART and the other has a return window.
- savsystems $30 experiment: still pending, not budget-counted
- Justification: market shock confirmed mid-purchase (WD sold out 2026, prices up ~46% since Sept 2025); two 12TB drives near the original $500 target is a defensible outcome in a market where one new 12TB drive is $300-440 retail at authorized channels. Original budget targeted a pre-shortage market that no longer exists.

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
