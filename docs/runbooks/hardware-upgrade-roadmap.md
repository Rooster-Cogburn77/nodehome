# Hardware Upgrade Roadmap

**Status:** Living document. Captures prioritized future hardware spends with concrete triggers, not a fixed plan.
**Last Updated:** 2026-05-13

The build is operationally complete as of Session 19. This roadmap covers what to spend on next, when triggers fire, and what to defer. Ordered by value-per-dollar in the current build state, not by absolute cost.

---

## Tier 1 — Near-term, high-value (next $400-500)

### UPS upgrade (replace the BX1500M)

**Current state:** APC Back-UPS Pro 1500VA (BX1500M), rated 900W output. System peaks at ~1255W under heavy 3-GPU inference. Inadequate for through-outage operation at load; only safe for graceful-shutdown buffer at idle/light load.

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

### Additional RAM (4× 32GB DDR4-2400 ECC RDIMM)

**Current state:** 128 GB in 4 of 8 DIMM slots. EPYC 7302P / H12SSL-i supports 256 GB with all 8 slots populated. 8-channel population doubles peak DRAM bandwidth.

**Trigger:** Any of:
- Fine-tuning workload lands (DeepSpeed ZeRO offload is memory-hungry)
- Dense stacked-services workload pushes RAM utilization >70% (currently ~10-15%)
- Large CPU-offload model experimentation (200B+ class)
- DDR4 ECC RDIMM market climbs further (the inflation-defensive case strengthens)

**Recommendation:** 4× Samsung M393A4K40CB1-CRC4Q (DDR4-2400 32GB 2Rx4 ECC RDIMM) to match the existing kit. ~$80-150/stick on eBay used server-pull. Total $320-600.

**Why this tier:** Speculative without a current workload pulling for it, BUT DDR4 ECC RDIMM is EOL category climbing. The defensive case is real, just not urgent.

**Cost:** $320-600 depending on sourcing and timing.

---

## Tier 3 — IPMI hardening enabler ($150-400)

### Managed switch + (optional) small firewall for management VLAN

**Current state:** BMC reachable only via in-band USB-NIC at `169.254.3.1/24`. Dedicated IPMI ethernet port is unpatched. `docs/runbooks/ipmi-hardening.md` captures the proactive scope; Phase 1 (password rotation + cert) needs no hardware, Phases 2-3 (management VLAN + static IP + cable patch) need this gear.

**Trigger:** Decision to execute IPMI hardening Phase 2/3 — currently deferred.

**Recommendation:** TP-Link TL-SG108E v6 (8-port smart-managed gigabit, 802.1Q VLANs) ~$35-50. Optional small firewall: Protectli Vault 2 (Intel-N100 / 4-port 2.5GbE running OPNsense) ~$200-300 if home router can't do VLAN trunking.

**Why this tier:** Real security upgrade for the BMC, but only valuable when executed. Hold until ready to do Phases 2-3.

**Cost:** $35-50 minimum (switch only); $200-300 full firewall stack.

---

## Tier 4 — Defer until specific need fires

### Storage expansion (16TB+ external)

**Current state:** Two 12TB drives landing this week (Drive #1 Walmart, Drive #2 PayMore). 24 TB total bulk capacity plus 2 TB NVMe. Comfortably matches near-term household media + photo + backup workload.

**Trigger:** Sustained >70% utilization of the 24 TB bulk array, OR a specific workload (Plex 4K library buildout, photo archive expansion past 2 TB) that demands more capacity.

**Defer:** No urgency. The 24 TB landing is sized for several years of growth.

### NVMe expansion (4-8TB via M.2 carrier card)

**Current state:** 2 TB Acer GM7 NVMe at ~10% utilization. M.2 slot supports up to 22110 form factor for a single bigger swap; alternatively an ASUS Hyper M.2 v2 card in an empty PCIe slot enables 4× M.2 via bifurcation.

**Trigger:** A workload that genuinely needs fast random I/O at scale — vector DB at scale, active fine-tuning dataset, KV-cache spillover for many concurrent serving sessions.

**Defer:** No current workload pulling for it.

### Networking upgrade (10GbE between AI node and laptop)

**Current state:** 1GbE on `eno2`. Sustained transfers between AI node and laptop limited to ~110 MB/s.

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
