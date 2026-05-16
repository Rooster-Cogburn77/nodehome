# Hardware Upgrade Roadmap

**Status:** Living document. Captures prioritized future hardware spends with concrete triggers, not a fixed plan.
**Last Updated:** 2026-05-16

The build is operationally complete as of Session 19. This roadmap covers what to spend on next, when triggers fire, and what to defer. Ordered by value-per-dollar in the current build state, not by absolute cost.

## Current Decision - 2026-05-15

Priority order changed after reviewing RAM price trajectory, local UPS reality, and network segmentation risk:

1. **GPU 3 proper cable remains the mandatory safety unlock.** No sustained 3-GPU/TP=3 load until the pigtail rule is retired.
2. **BMC/IPMI Phase 1 is the highest-priority security task because it is free.** Rotate the factory ADMIN password and clean up cert hygiene before the dedicated IPMI port is ever patched into LAN.
3. **RAM can jump ahead of UPS as the next spend if a clean matching 4x32GB RDIMM set appears at a sane price.** DDR4 ECC RDIMM has higher run-away-price risk than UPS or basic network gear.
4. **Network segmentation is important, and the cable-company router should be replaced.** First rotate BMC credentials/cert, then put the ISP box into bridge/modem mode if possible and move routing/VLAN control to owned gear.
5. **The current local UPS is acceptable for now as a graceful-shutdown/light-load buffer, not as peak-load ride-through.** Do not plan to run sustained multi-GPU inference through an outage on the BX1500M.

---

## Tier 1 — Near-term, high-value (next $400-500)

### UPS upgrade (replace the BX1500M)

**Current state:** APC Back-UPS Pro 1500VA (BX1500M), rated 900W output. System peaks at ~1255W under heavy 3-GPU inference. Inadequate for through-outage operation at load; only safe for graceful-shutdown buffer at idle/light load.

**Current decision:** Keep the local UPS for now as protection against blips and as a graceful-shutdown/light-load buffer. Do not size current operations around riding through an outage at peak inference load. If utility power drops while the node is above the UPS output rating, the UPS does not make the GPUs "load drop" automatically; it will likely alarm/overload and may cut output unless the host or operator stops workloads fast enough.

**Trigger:** Any of:
- Production MealMastery workload demands ride-through capability for power events
- Local power grid shows brownout/blip pattern that affects uptime
- Existing fallback (3600W Jackery) becomes inconvenient to keep wired in as buffer

**Recommendation:** Used APC SMT2200 (1980VA / 1980W, line-interactive, rackmount). ~$200-350 on eBay with confirmed-working / new-battery listings. Eaton 5P 2200 is equivalent alternative.

**Why this tier:** Real reliability gap, real spend justification, fits the next available budget cleanly with margin.

**Cost:** $200-350 used, $500+ new.

### GPU 3 cable backup (Super Flower SF-1600F14HT modular PCIe)

**Current state:** Primary order from eBay seller lizzieb753 (UK) is in transit; realistic window 2026-05-23 to 2026-06-10. Until it arrives, GPU 3 stays under the temporary pigtail rule (`docs/wiki/decisions/temporary-pigtail-rule.md`).

**Trigger:** Any of:
- lizzieb753 order delayed past 2026-06-15 OR shows lost-in-customs status
- Want fault-tolerance against a single-source cable failure

**Recommendation:** CableMod custom build (US-warehouse, rush + express shipping ~$70-100) OR equivalent Super Flower-compatible modular PCIe cable from a US-based eBay seller. Do NOT substitute EVGA / Corsair / Seasonic — pinout is brand-specific.

**Why this tier:** Small spend, eliminates single-point-of-failure on a critical path item. Either arrives first and becomes the primary, or sits as a spare.

**Cost:** $50-100.

---

## Tier 2 — Defensive against market trajectory ($300-500)

### Additional RAM (4x 32GB DDR4-2400 ECC RDIMM)

**Current state:** 128 GB in 4 of 8 DIMM slots. EPYC 7302P / H12SSL-i supports 256 GB with all 8 slots populated. 8-channel population doubles peak DRAM bandwidth.

**Trigger:** Any of:
- Clean matching Samsung M393A4K40CB1-CRC4Q set appears at a sane price
- DDR4 ECC RDIMM market climbs further
- Fine-tuning workload lands (DeepSpeed ZeRO offload is memory-hungry)
- Dense stacked-services workload pushes RAM utilization >70% (currently ~10-15%)
- Large CPU-offload / KV-cache-offload model experimentation becomes a real goal
- Rack/chassis CFD proof path grows past 128 GB through larger meshes, transient cases, retained timesteps, or ParaView/post-processing

**Recommendation:** 4x Samsung M393A4K40CB1-CRC4Q (DDR4-2400 32GB 2Rx4 ECC RDIMM) to match the existing kit. Prefer exact match; verify against H12SSL-i memory support and seller photos/part numbers before purchase.

**Why this tier:** Not an emergency capacity gap today, but DDR4 ECC RDIMM is the highest run-away-price risk in the remaining upgrade list. 256 GB also improves future CPU offload, long-context, multi-agent, service-stacking, and CFD headroom. For CFD specifically, more RAM helps capacity and post-processing comfort; it does not automatically make solves faster. Solver setup, geometry cleanup, boundary conditions, fan/heat assumptions, mesh convergence, and measured validation come first. Treat OpenFOAM-class CFD as CPU-first unless a GPU-native solver is deliberately selected.

**Cost:** ~$320-600 depending on sourcing and timing. Fast-move range: ~$300-450 for a clean matching 4x32GB set.

---

## Tier 3 — IPMI hardening enabler ($150-400)

### Router replacement + managed switch/AP for management VLAN

**Current state:** BMC reachable only via in-band USB-NIC at `169.254.3.1/24`. Dedicated IPMI ethernet port is unpatched. The current router is the standard cable-company router and is not a trustworthy long-term segmentation foundation. `docs/runbooks/ipmi-hardening.md` captures the proactive scope; Phase 1 (password rotation + cert) needs no hardware, Phases 2-3 (management VLAN + static IP + cable patch) need owned routing/switching gear.

**Current decision:** Network segmentation matters, but do not turn it into a vague all-at-once project. Execute Phase 1 first with no new hardware: rotate BMC ADMIN password, store it outside git, and clean up cert hygiene. Then replace the router/gateway layer instead of trying to build VLAN policy on the ISP router.

**Trigger:** Any of:
- Decision to execute IPMI hardening Phase 2/3
- Dedicated IPMI port is about to be patched into the rack network
- More services become reachable from devices beyond the trusted workstation
- ISP router can be placed into bridge/modem mode, or a separate approved modem path is chosen
- Home Wi-Fi needs to move off the ISP router

**Recommendation:** Preferred practical stack is Ubiquiti Cloud Gateway Ultra (~$129) + UniFi Switch Lite 8 PoE (~$109) + U7 Lite AP (~$99), with the ISP device in bridge/modem mode if possible. Estimated stack cost is ~$337 before tax/cables. Step up to Cloud Gateway Max only if the internet plan or internal-network plan needs >1Gbps / materially more 2.5GbE headroom. A cheaper TP-Link Omada path (ER605/ER707-M2 + Omada switch/AP) remains viable, but UniFi is the cleaner long-term control plane for this rack.

**Why this tier:** Real security upgrade for the BMC and a general home-network quality upgrade, but only valuable when executed as a gateway + VLAN/firewall + AP plan. Do not patch the dedicated BMC NIC into the general LAN first and clean it up later.

**Cost:** ~$337 before tax/cables for the recommended UniFi gateway + switch + AP stack; ~$466+ if stepping up to Cloud Gateway Max.

---

## Tier 4 — Defer until specific need fires

### Storage expansion (16TB+ external)

**Current state:** Two 12TB drives are in flight after Walmart canceled the original Drive #1. Replacement Drive #1 is a low-hour WD Easystore 12TB from sv2deals (`54` hours in seller SMART screenshot, serial `5PJHV96C`); Drive #2 is the PayMore WD My Book 12TB. If both validate on arrival, the node has 24 TB total bulk capacity plus 2 TB NVMe, comfortably matching near-term household media + photo + backup workload.

**Trigger:** Sustained >70% utilization of the 24 TB bulk array, OR a specific workload (Plex 4K library buildout, photo archive expansion past 2 TB) that demands more capacity.

**Defer:** No urgency. The 24 TB landing is sized for several years of growth.

### NVMe expansion (4-8TB via M.2 carrier card)

**Current state:** 2 TB Acer GM7 NVMe at ~10% utilization. M.2 slot supports up to 22110 form factor for a single bigger swap; alternatively an ASUS Hyper M.2 v2 card in an empty PCIe slot enables 4× M.2 via bifurcation.

**Trigger:** A workload that genuinely needs fast random I/O at scale — vector DB at scale, active fine-tuning dataset, KV-cache spillover for many concurrent serving sessions.

**Defer:** No current workload pulling for it.

### Networking upgrade (10GbE between AI node and laptop)

**Current state:** 1GbE on `eno2`. Practical SCP baseline captured 2026-05-14: node -> Windows `88.5 MB/s` (~708 Mbps), Windows -> node `67.8 MB/s` (~542 Mbps) using a 1 GiB file. Treat this as SSH/file-copy throughput, not raw line-rate; SCP encryption and Windows OpenSSH overhead can sit below the ~110 MB/s 1GbE file-copy ceiling.

**Trigger:** Repeated large-file workflows (sweep migration, dataset shuffling, model artifact pushes) that feel slow.

**Defer:** Niche; the existing 1GbE handles current Sweep+SSH+web workflows fine.

**If pursued:** Sabrent NT-P10G USB4 10GbE adapter (~$80-120) is the path that doesn't require a PCIe slot on the AI node — though there are empty PCIe slots available. PCIe-based 10GbE NICs (Mellanox ConnectX-3 / -4 used) are $20-50.

### PiKVM v4 (IPMI alternative / belt-and-suspenders management)

**Current state:** Supermicro BMC works fine as out-of-band management.

**Trigger:** BMC fails permanently, OR strong preference for open-source management stack.

**Defer:** IPMI is the cheaper and equivalently-capable path. PiKVM is duplication.

### Internal CA for BMC (Phase 4 of IPMI hardening)

**Current state:** BMC uses self-signed cert.

**Trigger:** Management VLAN has 3+ devices that all need certs (second-node future, additional rack gear).

**Defer:** Single-device certificate authority is over-engineering.

### Rack acoustic lining

**Current state:** BMC fan threshold cycling was fixed. Remaining noise concern is fan ramping / fan hunting, not a confirmed rack-panel resonance problem.

**Decision:** Do not buy adhesive acoustic foam for the rack interior. See `docs/wiki/decisions/rack-acoustic-treatment.md`.

**Trigger:** Only revisit physical acoustic material if a specific resonance is identified.

**If pursued:** Use rubber / neoprene isolation under external HDDs, blanking panels for airflow cleanup, or Dynamat-style butyl only on solid non-vented panels that audibly ring. Do not place foam near GPU exhaust, PSU exhaust, intake paths, or inside the RM400.

**Defer:** Fan ramping should be solved by measuring fan, temperature, and load behavior, not by lining the rack.

---

## Software / configuration upgrades (no spend)

These don't fit the hardware roadmap but are on the same opportunity-cost ledger when the build expands:

- Open WebUI repin from `:main` rolling tag to `:v0.9.5` explicit version (per `docs/runbooks/upgrade-cadence.md`)
- Persistent NVIDIA power-cap unit for the validated 2-GPU vLLM profile (`docs/runbooks/nvidia-power-cap.md`): apply `300 W` to GPUs 0 and 1 after driver load; leave GPU 2 untouched until the proper cable arrives.
- Ollama v0.30.0 evaluation when stable ships (currently rc15)
- vLLM v0.21.0 release notes review (TurboQuant KV-cache quantization)
- IPMI hardening Phase 1 (BMC password rotation, cert hygiene — runs in-band, no hardware needed)
- Healthcheck automation via sudoers NOPASSWD + cron
- Backup pipeline setup once Drives #1/#2 are mounted
- Sweep pipeline migration from laptop to AI node (shadow mode first)

---

## How to use this doc

When considering a hardware spend, before clicking Buy:

1. Check the trigger conditions for the item — has at least one actually fired, or is this speculative?
2. Re-read `docs/wiki/concepts/hardware-supply-2026.md` for current market context
3. Cross-check `docs/runbooks/upgrade-cadence.md` for any software-side review that's pending
4. Update this doc if a tier shifts or a new item should be added

The build's operational state is what matters more than the count of unspent dollars. Capital saved is optionality preserved; the wrong upgrade at the wrong time is dead money.
