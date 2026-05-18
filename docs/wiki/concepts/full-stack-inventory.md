# Full Stack Inventory

**Purpose:** Single cross-cutting reference for everything Nodehome is, is becoming, is considering, or is intentionally not building. Use this when you need the bird's-eye view that runbooks and `CURRENT_STATE.md` don't give in one place.

**Last reviewed:** 2026-05-18

**Companion docs (deeper detail per area):**
- Hardware: [`docs/runbooks/hardware-upgrade-roadmap.md`](../../runbooks/hardware-upgrade-roadmap.md)
- Nodechat: [`docs/runbooks/nodechat-scope.md`](../../runbooks/nodechat-scope.md), [`docs/runbooks/nodechat-terminal.md`](../../runbooks/nodechat-terminal.md)
- Live operator: [`docs/runbooks/live-mutations.md`](../../runbooks/live-mutations.md)
- Serving coexistence: [`docs/runbooks/ollama-vllm-coexistence.md`](../../runbooks/ollama-vllm-coexistence.md)
- AI History KB: [`docs/runbooks/ai-history-knowledge-base.md`](../../runbooks/ai-history-knowledge-base.md)
- Home media: [`docs/runbooks/home-media-server.md`](../../runbooks/home-media-server.md)
- IPMI: [`docs/runbooks/ipmi-recovery.md`](../../runbooks/ipmi-recovery.md), [`docs/runbooks/ipmi-hardening.md`](../../runbooks/ipmi-hardening.md)
- Power cap: [`docs/runbooks/nvidia-power-cap.md`](../../runbooks/nvidia-power-cap.md)
- BMC fan: [`docs/runbooks/bmc-fan-thresholds.md`](../../runbooks/bmc-fan-thresholds.md)
- Sweep upgrade cadence: [`docs/runbooks/upgrade-cadence.md`](../../runbooks/upgrade-cadence.md)

## Status legend

| Status | Meaning |
|---|---|
| **shipped** | Running today. Operational. |
| **in-flight** | Ordered or in transit. Decision committed; physical/external arrival pending. |
| **planned** | Decision made, scope clear, work not yet started. |
| **deferred** | On the roadmap with a specific trigger condition. Not started, not actively progressing. |
| **watch** | Logged for monitoring. No commitment to adopt. Re-evaluate when triggers fire. |
| **declined** | Considered and explicitly rejected with rationale. |

## When to update this file

- A `planned` item ships → flip its row to **shipped** and add an arrival date.
- A `deferred` item's trigger fires → reclassify as **planned** and add to the active work.
- A `watch` item gets independent reproduction / a usable artifact for our stack → propose **planned** with a runbook delta.
- A `shipped` item gets retired or replaced → move to a **Retired** section at the bottom or remove and note in `SESSION_LOG.md`.
- Bump the "Last reviewed" date when you make a substantive sweep through the file.

This is NOT the source of truth for any individual area — runbooks are. This is the cross-cutting roll-up.

---

## Hardware

| Component | Role | Status |
|---|---|---|
| Supermicro H12SSL-i v2.0 | Motherboard, 128 PCIe Gen4 lanes for 3-GPU scalability | shipped |
| AMD EPYC 7302P (16-core) | Server-class CPU with the lane budget for 3-card builds | shipped |
| 128GB DDR4-2400 ECC RDIMM (Samsung M393A4K40CB1-CRC4Q) | System RAM with ECC for long-running inference | shipped |
| 3× RTX 3090 Turbo (blower) | Inference compute (GPU0+1 production, GPU2 pigtail-restricted) | shipped (GPU2 restricted) |
| Super Flower SF-1600F14HT 1600W Titanium PSU | Power for full 3-GPU + EPYC load | shipped |
| Acer Predator GM7 2TB TLC NVMe | OS + Docker volumes + model cache | shipped |
| SilverStone RM400 chassis | 4U rackmount for the build | shipped |
| Noctua NH-U9 TR4-SP3 | CPU cooler | shipped |
| SysRacks 24×24 rack | Physical mount | shipped |
| Tedgetal 1U sliding shelf (U3-U6) | Box mounts on this | shipped |
| 1U cantilever shelf (U7) | Storage drive shelf | shipped |
| APC Back-UPS XS 1500M | Power blip buffer + graceful shutdown signal | shipped |
| APC USB comms cable | UPS telemetry to host via NUT | shipped |
| 2× WD 12TB external USB HDDs (sv2deals Easystore + PayMore My Book) | Media library storage | in-flight (arrival window 2026-05-16 to 2026-05-20) |
| SF-1600F14HT PCIe modular cable (lizzieb753 UK eBay) | GPU3 power, retires pigtail rule | in-flight (arrival window 2026-05-23 to 2026-06-10) |
| 4× 32GB DDR4-2400 ECC RDIMM (additional set) | RAM upgrade if clean opportunity appears at sane price | deferred (price/availability trigger) |
| APC SMT2200 (used) | Production UPS sized for sustained 2-GPU inference ride-through | deferred (no fixed trigger) |
| UniFi Cloud Gateway Ultra + Switch Lite 8 PoE + U7 Lite AP | Owned network gear, bypasses/replaces Spectrum `SAX1V1S` router and provides management VLAN foundation | planned (separate Spectrum modem confirmed; spend pending) |
| Second top fan (AC Infinity MULTIFAN S5) | If TP=3 sustained load exceeds 80°C on GPU0 | deferred (trigger: GPU0 plateau >80°C under TP=3) |
| PiKVM v4 | Out-of-band KVM hardware | deferred (Tier 4) |
| 10GbE switch + NIC | Network throughput upgrade beyond 1GbE | deferred (Tier 4) |
| NVMe expansion via Hyper M.2 card | Additional NVMe slots | deferred (Tier 4) |
| Internal CA hardware | TLS for internal services | deferred (Tier 4) |
| Motherboard standoff screws (final fit-out) | Mechanical follow-on when chassis next opens | deferred (next chassis-open event) |
| 14TB WD My Book (ramen_scorpion offer) | Asymmetric pool problem, international shipping; waiting on offer expiry | declined |

## OS + base infrastructure

| Component | Role | Status |
|---|---|---|
| Ubuntu Server 26.04 LTS | Host OS | shipped |
| Linux kernel 7.0.0-15-generic | Kernel | shipped |
| NVIDIA driver 595-server-open + CUDA 13.2 | GPU stack | shipped |
| Docker CE 29.1.3 + nvidia-container-toolkit 1.19.0 | Container runtime + GPU passthrough | shipped |
| OpenSSH | Remote admin from Windows workstation | shipped |
| systemd | Service supervision | shipped |
| NUT (nut-driver + nut-server + nut-monitor) | UPS comms daemon | shipped |
| `nvidia-power-cap.service` | Persistent 300W cap on GPU0+1 at boot | shipped |

## Inference / serving stack

| Component | Role | Status |
|---|---|---|
| Ollama v0.23.2 | Single-GPU interactive lane (`mistral-small3.1:24b` daily driver, ~51 tok/s) | shipped (GPU0+1 only, GPU2 excluded by `CUDA_VISIBLE_DEVICES=0,1`; large-model loads can still hit VRAM pressure while vLLM is resident) |
| vLLM v0.19.1 (Docker) | Multi-GPU production (`Qwen2.5-32B-Instruct-AWQ` on TP=2, ~59 tok/s) | shipped (GPU0+1, 300W cap, top fan) |
| Open WebUI (Docker, `ghcr.io/open-webui/open-webui:v0.9.5`) | Browser UI for both Ollama + vLLM | shipped (pinned 2026-05-16) |
| llama.cpp (direct) | Benchmark/watch path only, not production | watch |
| vLLM TP=3 + 70B-class AWQ (e.g. `Qwen/Qwen2.5-72B-Instruct-AWQ`) | Future 3-GPU production once cable lands | deferred (gated on SF-1600F14HT cable) |

## Local model inventory (~98 GB on disk)

| Model | Size | Lane |
|---|---|---|
| `qwen3:8b` | 5.2 GB | smoke / fast |
| `mistral-small3.1:24b` | 15 GB | **daily driver** (Ollama fast lane) |
| `gemma3:27b` | 17 GB | alt interactive |
| `qwen2.5:32b-instruct-q4_K_M` | 19 GB | alt interactive (Ollama) |
| `llama3.3:70b-instruct-q4_K_M` | 42 GB | deep lane (8-15 tok/s layer-split) |
| `Qwen/Qwen2.5-32B-Instruct-AWQ` | (vLLM weights) | strong production (~59 tok/s TP=2) |

## Custom Nodehome tooling

| Component | Role | Status |
|---|---|---|
| **Nodechat** (`scripts/nodechat.py`) | Local agentic terminal: chat + history/repo/web/live auto-routing, one-shot slash commands, /apply edits, /approve queue for git + live mutations, model profiles + auto-routing + remote profiles (env-gated), persistent JSONL audit | shipped (homelab `/live journal ollama` one-shot smoke passed 2026-05-18) |
| **AI History KB** (`scripts/ai_history_kb.py`) | Private SQLite FTS of all Claude/Codex/Claude Code history (~280K items), HTTP API on `:8765` | shipped |
| **`ai-history-kb.service`** | Persistent host API systemd unit | shipped |
| **`scripts/healthcheck.sh`** | One-shot stack health view (GPU, storage, services, BMC, audit, kernel-error) | shipped |
| **Sweep pipeline** (`sweeps/*.py`) | Daily/extended source ingest → fact notebook → wiki → operator brief → LLM synthesis → digest → email | shipped |
| **Manual article inbox** (`sweeps/manual_article_inbox.py`) | Operator-curated link queue into extended digest. **Manual inbox renders the current ignored queue every extended/all run** (semantic difference from normal RSS sources). | shipped |
| **`scripts/openwebui/ai_history_tool.py`** | Open WebUI tool wrapper calling the AI History API | shipped |
| **Windows launchers** (`scripts/windows/nodechat*.cmd`) | Workstation entry points for Nodechat + SSH tunnel | shipped |
| Static publication site (`site/`) | nodehome.ai branding for digest, future blog | partial (assets exist, deployment status not fully tracked) |

## Media stack (mostly not installed)

| Component | Role | Status |
|---|---|---|
| Jellyfin (Docker) | Stream movies/TV to household clients; NVENC transcoding via 3090s | planned (day-1 after drives arrive + SMART-verify) |
| Sonarr | Auto-grab TV episodes from indexers | planned (Phase 2, optional) |
| Radarr | Auto-grab movies | planned (Phase 2, optional) |
| Prowlarr | Central indexer manager (single config across all *arrs) | planned (Phase 2, recommended) |
| SABnzbd **OR** qBittorrent+gluetun | Download client (NZB or torrent path; pick one) | planned (Phase 2) |
| Seerr (formerly Jellyseerr/Overseerr — same project after 2026 merger) | Household request UI on top of Sonarr/Radarr + Jellyfin | planned (Phase 2, optional) |
| Bazarr | Auto-subtitle download/sync from OpenSubtitles/Subscene/etc. | planned (Phase 2, install if household uses subs habitually) |
| Lidarr | Music auto-grab | declined unless music need surfaces |
| Tdarr / Unmanic | Background re-encode library to HEVC/AV1 for storage savings | watch |
| Cross-Seed, Autobrr, Notifiarr, Tautulli | Niche additions | watch |

**Recurring cost** for the *arr stack (not in original `home-media-server.md` budget): ~$5-15/month
- Usenet path: provider (~$5-10/mo) + indexer (~$10-25/yr)
- Torrent path: VPN (~$5-10/mo) + free public trackers or invite-only private trackers

## Backup / data integrity

| Component | Role | Status |
|---|---|---|
| Restic | Encrypted snapshot backups for irreplaceable data (photos, configs, Nodechat sessions, AI History DB) | planned (after drives arrive) |
| `smartctl` checks | Drive health on USB-attached media drives, plus existing NVMe | planned |
| Backup target disk | One of the 12TB drives, eventually | planned |
| `smartd` alerts | Continuous SMART monitoring with email/notification | deferred |

## Security / operational hardening

| Component | Role | Status |
|---|---|---|
| BMC/IPMI Phase 1 | ADMIN password rotation completed 2026-05-17; live credential is in KeePassXC. Cert hygiene remains pending before any LAN patch. | partial (password done; cert hygiene pending) |
| BMC/IPMI Phase 2 | Management VLAN network plumbing | deferred (gated on UniFi gear and Spectrum router bypass) |
| BMC/IPMI Phase 3 | Static IP + dedicated NIC patch into LAN | deferred (gated on Phase 2) |
| BMC/IPMI Phase 4 | Internal CA for trusted BMC certs | deferred (Tier 4) |
| Healthcheck automation | Narrow sudoers-NOPASSWD systemd timer instead of manual `/live healthcheck` | planned |
| Reverse proxy (Traefik / Caddy / Nginx Proxy Manager) | If/when services need to be reachable beyond LAN | deferred (no remote exposure planned today) |
| Authelia / Authentik SSO | If running >3 web UIs and exposing them | deferred (gated on remote exposure decision) |
| `live-mutations.md` allowlist | Operator approval queue for selected service restarts (vllm-server, open-webui, ollama via sudoers) | shipped |

## Sidecar / personal tools

These are useful adjacent ideas, but they are not Nodehome core serving, AI research, or sweep/publication work. Keep implementation, secrets, and state outside this repo unless a future decision explicitly changes scope.

| Component | Role | Status |
|---|---|---|
| Data-broker opt-out automation (`stephenlthorn/auto-identity-remove` candidate) | Personal privacy automation for people-search/data-broker opt-outs | watch/sidecar (separate repo only; upstream is macOS-oriented and uses CapSolver, which is a third-party privacy leak unless removed/replaced) |

## Newsletter / publication

| Component | Role | Status |
|---|---|---|
| Sweep digest (daily core + extended) | Auto-curated AI-stack news → email, sectioned by lane | shipped |
| Resend (HTTP API) | Outbound email transport | shipped |
| BCC pattern | Subscriber privacy: visible-to is `digest@nodehome.ai`, real recipients hidden | shipped |
| LLM synthesis pass | Local model writes 1-paragraph summary at top of digest | shipped |
| Operator brief | Internal triage view (not emailed) | shipped |
| nodehome.ai static site | Public-facing brand for digest and future blog | partial / in-flight |

**Hard rule from `CLAUDE.md` Rule 8:** No agent (Claude Code, Codex, Nodechat, or future) may send live external communications by inference. See Rule 8 for the exact authorization boundary.

## Watch lane (logged, not installed)

### Memory architecture
- **δ-mem** (arXiv 2605.12357) — model-internal online memory complementing RAG. Watch until a Qwen 32B+ checkpoint, independent reimplementation, or vLLM/SGLang integration appears.

### Serving / inference acceleration
- **Orthrus** (`chiennv2000/orthrus`, arXiv 2605.12825) — lossless 4-5× parallel decoding via dual-view (AR + diffusion). Watch until Qwen3-14B+/32B Orthrus weights ship, vLLM/SGLang integration lands, or independent reimplementation. Optional lab-only benchmark allowed under gates (stop vllm-server, no GPU2, Docker over venv, correctness before speed, 4h timebox; see `docs/wiki/research/inference-architectures.md`).
- **SANA-WM** (`NVlabs/Sana`, arXiv 2605.15178) — 2.6B controllable 720p minute-scale world/video model from image + prompt + 6-DoF camera trajectory. Watch/use-candidate only; strongest local claim is RTX 5090 + NVFP4, so current 3× RTX 3090 stack needs a bounded lab test before any capability claim. See `docs/wiki/research/inference-architectures.md`.

### Long-context architectures
- **SubQ** (Appen/SSA) — hosted 12M-token long-context system. Watch only; waitlist requested.

### Orchestration / agent infrastructure
- **whichllm** (`Andyyyy64/whichllm`) — model-scout/planning CLI. Use planning/JSON mode only; never `whichllm run` while GPU2 pigtail rule is active.
- **Sakana Conductor** — manager-of-models orchestration paper.
- **Cloudflare agent provisioning + Stripe Projects** — agent-operated infrastructure pattern.
- **Railway changelog #0288** — agent-guardrails signal (reversible destructive actions, shared machine identity).

### Release-watch / upgrade-review queue
- **vLLM v0.20.x / v0.21.x** — current pin v0.19.1
- **Ollama v0.23.3 / v0.30.x** — current pin v0.23.2
- **llama.cpp b9010+** — CUDA multi-GPU fixes
- **Open WebUI** — pinned to `v0.9.5` on 2026-05-16; post-migration backup is `/home/bmoore_77/open-webui-backups/open-webui-v095-postmigration.tgz`

### Hosted models / routing
- **Kimi K2.6** — large hosted model; not practical on 3× 3090
- **Qwen3.6-Max-Preview** — hosted proprietary coding model
- **llm-openrouter 0.6** — routing/fallback tooling

### Marketplace / economics
- **GPU rental** (Vast.ai / Clore / Akash) — logged not as a pivot. 3× 3090 economics: ~$160-330/mo net at typical pricing/utilization, not the "$3K/mo" the source post claimed. Conflicts with own-use availability + UPS sizing + pigtail rule. Re-evaluable only after cable retires the pigtail rule AND BMC hardening AND deliberate network isolation. See `docs/wiki/research/gpu-rental-economics.md`.

## Validation backlog (planned work, not infra components)

| Item | Role | Status |
|---|---|---|
| Power consumption baseline (Kill-A-Watt or smart plug) | Real wall-power measurement at idle / vLLM idle / 2-GPU load / 3-GPU load. NUT `ups.realpower` only measures what's plugged into the UPS; main rig is on wall power directly, so UPS telemetry alone does not cover this. | planned |
| 2-GPU vLLM thermal soak (300W + top fan) | Complete/pass. Production posture validated. | shipped |
| Network throughput baseline | SCP baseline captured (~88 MB/s node→Win, ~67 MB/s Win→node). True `iperf3` baseline optional. | partial |
| Release-notes review (vLLM 0.21.x / Ollama 0.30.x) | Before any upgrade-pin move | planned |
| RAM stress test | Lower urgency since the box has been running on the RDIMMs | deferred |
| NVMe non-destructive `fio` benchmark | Use `--filename=` against mounted FS, never raw `/dev/nvme0n1` | planned |
| 3-GPU TP=3 thermal/power soak | Gated on SF-1600F14HT cable arrival | deferred |
| 70B-class AWQ TP=3 benchmark | Gated on SF-1600F14HT cable arrival | deferred |
| ReBAR A/B (Above 4G Decoding stays on, ReBAR currently off) | Gated on stable 3-GPU baseline | deferred |
| Routing corpus growth | Maintenance loop for Nodechat auto-routing (currently all 4 routers at 1.000/1.000 on 102-prompt corpus) | ongoing |

## Rough composition

- ~70% of the planned stack is shipped today
- ~20% is gated on physical arrivals (drives, GPU3 cable)
- ~10% is genuine "later" work (BMC hardening, network segmentation, backup pipeline)

The watch lane is intentionally larger than the shipped lane — that's the point of the sweep system: track what's emerging without committing to it.
