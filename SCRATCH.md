# Session Scratch - 2026-05-11 (Session 17)
Focus: Home media server planning — scoped a $500 spend on bulk storage to support a household TV/movie library on the existing AI node. No second compute node introduced. Continuation of Session 16's clean rack install + fan threshold fix.

## What was decided this session
- **Architecture:** direct-attached USB storage on the AI node, mounted into the existing Docker stack. Jellyfin container handles the media library; TV-side clients (smart TV apps / Roku / Apple TV / Fire Stick) stream over the home network. No second compute node.
- **Hardware spec:** 2× WD Easystore 12TB external USB 3.0 drives, ~$420 total. Two drives so single-drive failure loses half the library, not all of it. Media is replaceable, so internal redundancy via ZFS mirror is not required — "two copies by policy" for the irreplaceable subset (photos, MealMastery configs) handled later.
- **Software stack:** Jellyfin (preferred over Plex — fully free, no remote-stream paywall, mature). Optional automation stack (Sonarr/Radarr/Jellyseerr/Bazarr) can be added later as Docker containers.
- **3090 HDMI ports stay unused.** Headless server posture preserved; BIOS primary display stays on the onboard ASPEED VGA. The 3090s still do the heavy lifting via NVENC for transcoding, but as compute devices over the network, not as display devices via HDMI.

## What was explicitly considered and rejected
- **Second-node compute box** (M75q-1 + USB drive or similar) — over-engineered for a media-only use case once user clarified they don't want second-node operational overhead.
- **Synology / QNAP NAS appliance** — $230-380 chassis consumes most of the $500 before any drives.
- **Internal HDDs in the RM400** — drive cages removed in Session 16; only 1× internal 2.5" SATA bay remains, can't fit 2× 3.5" NAS drives.
- **More RAM (128 GB → 256 GB)** — user has 115 GB unused headroom on existing 128 GB. RAM is over-provisioned for current and near-term workloads. Inflation-lens argument doesn't override "you won't use it" — speculative RAM is dead capital.
- **2× 8TB drives in ZFS mirror over USB** — known reliability issues (USB enclosure sleep, controller hangs trip ZFS). Codex's "two copies by policy" is the safer pattern for USB-attached storage.
- **Plug a TV directly into a 3090 HDMI** — requires BIOS primary-display change + OS-side desktop environment, breaks the headless posture. Network streaming via Jellyfin client apps is the standard pattern.

## Key correction taken this session
- User pushed back on my "drives, RAM, switches keep getting cheaper, buy when needed" framing. Reality: DDR4 ECC RDIMM, HDDs, used server hardware are all *climbing* in price, not dropping. Updated reasoning to "lock in capacity at today's prices where you'll actually use it" — but **only** for resources the user will actually deploy. Speculative buying ahead of need on an item with no current use case is still dead capital, even with prices climbing.
- Also: I drifted into a "second-node + storage" narrative once home-server use cases came up. User had to push back twice before I re-ranked from scratch and landed on direct-attached storage (no second node). Lesson: re-rank periodically when a conversation starts converging on a particular architectural direction, to avoid path-lock-in the user didn't actually ask for.

## Documented this session
- `docs/runbooks/home-media-server.md` — scope/plan doc covering architecture, hardware spec, software stack, what's out of scope, open items before purchase, order of operations for install day. Companion to the IPMI hardening scope doc from Session 16.

## Open items before purchase
- Confirm Best Buy / Amazon stock and exact pricing on order day. WD Easystore pricing fluctuates with sale cycles; 14TB sometimes drops within $20-30 of 12TB and becomes the better $/TB pick.
- Confirm 2× USB 3.x ports available on the AI node and 2× outlets in the rack area (each Easystore needs its own AC brick).
- Decide library layout: TV on one drive + movies on the other, or both as primary with year/alphabetical split, or one primary + one as backup-of-irreplaceable.
- Confirm Jellyfin vs Plex (default: Jellyfin).

## Out of scope for this $500 (separately planned)
- **Backup of irreplaceable data** (photos, MealMastery configs, sweep state). Media itself is replaceable; doesn't need backup. The small irreplaceable subset (~50-200 GB) can later use a partition of Drive 2 as a Restic target without buying anything else.
- **UPS upsize.** BX1500M is undersized; user has 3600W Jackery as fallback buffer. Out of scope for this $500.
- **Storage growth past 24 TB.** When the library outgrows two drives, the upgrade path is either adding a third drive to the same setup, or migrating to a NAS appliance / DAS enclosure with larger drives.
- **IPMI hardening Phase 2/3.** Separate networking spend; scope already captured in `docs/runbooks/ipmi-hardening.md`.

## Carried forward from Session 16
- Permanent in-chassis install complete, board screws now all in (per Session 16 follow-on).
- Rack install complete on Tedgetal sliding shelf.
- BMC fan threshold fix landed and documented at `docs/runbooks/bmc-fan-thresholds.md`.
- Healthcheck output clean from rack-install validation: 3 GPUs at P8 idle, both Docker containers up, both APIs serving 200, BMC reachable via USB-NIC.
- Option C resolved: Open WebUI routes to both Ollama and vLLM with a per-model system prompt grounding Qwen in the local hardware.
- GPU 3 cable still in transit; temporary pigtail rule still enforced via Ollama `CUDA_VISIBLE_DEVICES=0,1`.
- JF1 pinout still not photographed into a runbook (next chassis-open event).

## Operational lessons added this session
- **Re-rank fresh when narratives start to converge.** When a conversation about $500 spend drifted into "second-node + storage," I followed the narrative instead of re-checking whether the original ranking was still right. User had to push back twice to break the drift. Save as feedback memory: periodically re-rank options from scratch during a long planning conversation, especially after the user reframes the use case.
- **Don't quote prices off old assumptions.** Multiple times this session I quoted drive / chassis / RAM prices that were lower than the actual current market. The market for legacy DDR4 ECC RDIMM and NAS-tier HDDs has tightened. Check actual listings before quoting price ranges in a market-sensitive recommendation.
