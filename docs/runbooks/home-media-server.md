# Home Media Server — Scope and Plan

**Status:** PROCUREMENT / VALIDATION IN PROGRESS — architecture decided; two 12TB external drives ordered; PayMore WD My Book has passed initial + short SMART, install waits on both-drive validation.
**Authored:** 2026-05-11 (Session 17 planning).

## Goal

Stand up a household-scale media library (TV shows + movies) on the existing AI node, accessible to TVs, phones, and laptops across the home network. Use the existing 3× 3090 hardware (NVENC transcoding) and existing Docker stack. **Do not introduce a second compute node** for this — the user explicitly clarified they don't want second-node operational overhead for the media use case.

## What we decided

### Architecture: direct-attached storage on the AI node

Drives plug into the AI node via USB and mount as `/mnt/storage` (or similar). The AI node runs the media-server container (Jellyfin, recommended over Plex — fully free, no remote-stream paywall, mature). Clients (smart TVs, phones, laptops) stream from the AI node over the network using Jellyfin native apps.

**Explicitly rejected alternatives:**
- **Synology / QNAP NAS appliance** — clean but $230-380 for the chassis alone consumes most of the budget before any drives.
- **Thin-client + USB DAS as "second node"** — over-engineered for a media-only use case; user clarified second-node services separation is not a priority.
- **Internal HDDs in the RM400** — drive cages were removed in Session 16; only 1× internal 2.5" SATA bay remains.
- **Plug TV directly into a 3090 HDMI port** — possible but requires BIOS primary-display change and OS-side display config. Network streaming via Jellyfin client apps is the standard pattern and works without modifying the headless server setup.

### Hardware spec

| Item | Count | Source | Approx cost |
|---|---|---|---|
| WD Easystore 12TB external USB 3.0 desktop HDD | 2× | Best Buy / Amazon / B&H | $200-220 each (~$420 total) |
| **Total** | | | **~$420** |

### Procurement state — updated 2026-05-18

- Walmart order `2000146-01251834` for WD My Book 12TB (`WDBBGB0120HBK-Newm`) was canceled as out of stock; `$269.54` temporary hold should release within 10 business days.
- Replacement Drive #1 is WD Easystore 12TB (`WDBAMA0120HBK`) from eBay seller `sv2deals`, accepted offer `$220` plus `$13.16` listed shipping. Listing SMART screenshot: `WDC WD120EDAZ-11F3RA0`, serial `5PJHV96C`, `54` power-on hours, `15` power cycles, zero reallocated / pending / uncorrectable / UDMA CRC errors. Verify same serial and counters on arrival before formatting.
- Drive #2 is WD My Book 12TB from PayMore Westport / SPEEKS Technology, eBay order `03-14645-30973`, `$259.79` total with return window through June 19. It arrived 2026-05-18 and enumerated as `1058:25ee Western Digital Technologies, Inc. My Book 25EE`; Linux sees `/dev/sda` as `WDC WD120EDGZ-11CMZA0`, vendor `WD`, serial `T3G0WU1E`, transport `usb`. `smartctl -d sat -a /dev/sda` identified it as Western Digital Ultrastar (He10/12) family, 12.0 TB, 7200 rpm, helium (`Helium_Level` present), SMART `PASSED`, `Power_On_Hours 0`, `Power_Cycle_Count 5`, and zero reallocated / pending / offline uncorrectable / UDMA CRC errors. Short offline self-test completed without error at lifetime hour 0. Long SMART test remains pending before final acceptance/formatting.
- Known subtotal before any sv2deals tax: `$492.95`; final all-in total depends on eBay tax.

Why **2× 12TB**:
- Best $/TB at this price point (~$18-22/TB)
- 24 TB total raw capacity comfortably hosts a serious enthusiast-tier library (10-20 TB realistic working size)
- Two physical drives distribute single-drive failure risk — losing one drive loses half the library, not all of it
- Both drives can serve as primary storage initially (media is replaceable); one can later be repurposed as Restic backup target for irreplaceable data (photos, configs) without buying anything else
- Comfortably under the $500 budget ceiling; leaves $80 in reserve

Alternative considered but rejected:
- **1× 24TB single drive** (~$420-500) — same capacity, single point of failure for the whole library. Cleaner physically (1 cable, 1 brick) but worse risk distribution.
- **2× 14TB Easystore** (~$500-560) — slight budget stretch, $20-30 less per TB, viable if user wants to stretch.
- **2× 8TB drives in ZFS mirror over USB** — discarded; ZFS mirror over USB has known reliability issues (enclosure sleep, USB controller hangs).

### Software stack

All run as Docker containers on the AI node alongside the existing vLLM / Ollama / Open WebUI stack:

| Service | Purpose | Required? |
|---|---|---|
| **Jellyfin** | Media server with web UI + native apps for smart TVs, phones, laptops. NVENC transcoding via the 3× 3090s. | Yes |
| **Sonarr / Radarr / Lidarr** | Optional library automation (auto-rename, organize TV/movies/music) | Optional |
| **Jellyseerr** | Optional household request UI for asking for new content | Optional |
| **Bazarr** | Optional subtitle automation | Optional |

Plex is also viable but loses to Jellyfin on cost (Plex Pass paywalls remote streaming) and openness. No technical reason to pick Plex over Jellyfin for this build.

### Why network streaming, not HDMI from the rack

The 3× 3090s have HDMI/DisplayPort outputs on the back. They are **not used** in this design:

- The H12SSL-i's onboard ASPEED VGA is the BIOS primary display; the 3090 HDMI ports are electrically dead unless BIOS is reconfigured.
- Plugging a TV directly into a 3090 HDMI would require BIOS changes + an OS-side desktop environment, breaking the headless server posture.
- Standard pattern: server stays headless in the rack, TV-side clients (smart TV apps, Roku, Apple TV, Fire Stick) stream from the server over LAN.
- 3090s still do the heavy lifting via NVENC hardware transcoding when a TV requests a format the source isn't in — but they do it as compute devices, not display devices. NVENC and HDMI output are independent functions on the same GPU.

## What this does NOT solve (in scope to address separately later)

- **Backup for irreplaceable data.** Photos, MealMastery configs, sweep state — these need their own backup story. The media library itself is replaceable (re-rip, re-download), so it does not need redundancy. Recommended later: dedicate Drive 2 partially as a Restic backup target for the small irreplaceable subset (~50-200 GB total), keep the rest as primary media capacity.
- **UPS upsize.** The BX1500M is undersized for full-load operation. Out of scope for this $500; user has a 3600W Jackery as fallback buffer.
- **Storage for Immich (photos) at scale.** If photo ingest grows past 1-2 TB, may need dedicated photo storage. Plenty of headroom in 24 TB for years of photo growth.
- **IPMI hardening Phase 2/3.** Separate networking spend, not part of this scope.

## Open items before install

- No additional drive purchase is planned unless one incoming drive fails arrival verification.
- Confirm USB ports available on the AI node (need 2× USB 3.x). Each Easystore needs its own AC brick — plan rack outlet capacity.
- Decide library layout on the drives:
  - Option 1: Drive 1 = TV, Drive 2 = movies (clear separation)
  - Option 2: Drive 1 = primary library, Drive 2 = backup-of-Drive-1 + irreplaceable backups (more redundancy)
  - Option 3: Both as primary, split alphabetically or by year
- Decide on Jellyfin vs Plex (default: Jellyfin per above).
- Decide on optional automation stack (Sonarr/Radarr/Jellyseerr) — can be added later, not needed for day-1.

## Order of operations once drives arrive

1. Plug both drives into AI node USB 3.x ports. Confirm they enumerate (`lsblk`).
2. Run arrival SMART before formatting. Drive #2 (`/dev/sda`, serial `T3G0WU1E`) has passed initial + short SMART; run/pass long SMART before accepting it. Drive #1 (`5PJHV96C`) still needs arrival verification.
3. Format as ext4 (or btrfs if you want snapshots). Mount as `/mnt/media1` and `/mnt/media2`. Add to `/etc/fstab`.
4. Create directory structure per chosen library layout.
5. Pull `jellyfin/jellyfin` Docker image. Run container with volume mounts to the drives and GPU passthrough for NVENC.
6. Configure Jellyfin via web UI: add libraries pointing at the mount paths.
7. Install Jellyfin client app on TVs/phones/laptops; connect to the server's local IP.
8. Begin ingesting content.
9. (Optional later) Add Sonarr/Radarr/Jellyseerr/Bazarr automation stack.
