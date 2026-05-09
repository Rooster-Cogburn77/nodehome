# Current State

**Last Updated:** 2026-05-09

## Active Work
- Hardware bring-up is now well past POST. `Supermicro H12SSL-i` BIOS `3.3` / build `03/28/2025` / CPLD `F0.A6.47`, BMC firmware `01.05.02`, IPMI Working, all four `Samsung M393A4K40CB1-CRC4Q` RDIMMs trained at `Total Memory: 128 GB`.
- **Ubuntu Server 26.04 LTS is installed on `BLK0` (the Acer Predator GM7 2TB NVMe) and boots cleanly from NVMe.** Kernel is `Linux 7.0.0-15-generic`, hostname `homelab`, OS partitions are `/boot/efi` (1 GiB FAT32) + `/` (1.86 TiB ext4). System is fully patched.
- **Network is operational on `eno2`** (Broadcom BCM5720, MAC `90:5a:08:7b:73:55`, DHCP `192.168.1.198/24`, dual-stack with IPv6). SSH reachable from the user's workstation; the IPMI KVM is no longer needed for day-to-day work. `eno1` is intentionally unused (no cable). The BMC USB virtual NIC `enxbe3af2b6059f` at `169.254.3.1/24` is harmless.
- **GPU #1 (`81:00.0` in `CPU SLOT1`) and GPU #2 (`C1:00.0` in `CPU SLOT3`) are installed and fully validated.** Both `NVIDIA GeForce RTX 3090` (GA102), driver `nvidia-driver-595-server-open` at runtime version `595.58.03`, CUDA runtime `13.2`. Both slots negotiated PCIe `gen.max = 4`, `width.max = 16`, and **GPU 0's link was confirmed to actually run at Gen 4 x16 under inference load** (idle Gen 1 → Gen 4 ramp captured via `nvidia-smi` mid-flight). Power delivery held cleanly at `348 W` (essentially the 350 W TDP cap) for an 89% utilization sustained inference run, validating the 2-cable / one-head-per-dual-head-cable power configuration.
- **Day-one inference path is working end-to-end on the 2-GPU configuration.** Ollama is installed and the systemd service is active. `qwen3:8b` (~5 GB weights, ~10.9 GiB resident on GPU 0 because the default `num_ctx=262144` allocates a large KV cache) ran a real CoT prompt and returned clean output. Multi-GPU detection is confirmed at the framework level — Ollama sees both 3090s as `compute=8.6` CUDA devices and pools 48 GB VRAM.
- **GPU #3 is the only remaining hardware item.** The card is on hand but a proper full install is blocked on a single missing PCIe modular cable for the `Super Flower SF-1600F14HT` (Leadex Titanium 1600W) PSU. Sourcing options: eBay `"SF-1600F14HT" cable`, CableMod configurator with PSU set to Super Flower Leadex, or Super Flower USA distributor email. Do **not** substitute EVGA Supernova / Corsair / Seasonic cables — Super Flower Leadex Titanium pinout is brand-specific and cross-brand mixing has well-documented fry incidents.
- A **temporary pigtail rule is allowed for GPU #3 only** while the proper cable is in transit, governed by `docs/wiki/decisions/temporary-pigtail-rule.md`. Permitted use is bounded to BIOS / `lspci` / driver install / `nvidia-smi` / brief supervised low-load smoke tests, with touch-checks on cable and connectors. **Not permitted** under the temporary rule: long inference, unattended operation, stress tests, benchmarks, or any sustained multi-GPU load. The rule retires the moment the proper cable is installed.
- Ollama install actually placed `v0.23.2` on disk (the install script always pulls latest stable); this is the previously-reviewed-clean release that earlier sweeps decided did not justify churning the pin pre-bring-up. The pin is therefore moved from `v0.21.2` to `v0.23.2` on 2026-05-09 to match what is actually running, rather than pretending the install matches a stale pin.
- Known BIOS tuning item still open: `Re-Size BAR Support` remains `[Disabled]` while `Above 4G Decoding` is `[Enabled]`. ReBAR is the natural pairing for 3x RTX 3090 inference and should be A/B tested as a deliberate change after the third GPU is online and a stable baseline benchmark exists, not flipped blind.
- **Physical deployment state is partial.** Components are mounted inside the `SilverStone RM400` chassis (not on a breadboard), but the RM400 itself is currently sitting on a desk, not rail-mounted in the `SysRacks 24x24` server rack. Cable routing inside the chassis is functional but not yet final-tidied — power and PCIe cables are connected and validated under load, but cable management for a permanent install (ties, channels, strain relief on the rear I/O panel) has not been done. The dedicated IPMI ethernet port is also not yet patched into the rack-side network — IPMI is currently reachable only via the host OS's BMC virtual NIC, which is fine for bring-up but not for true out-of-band management. Final deployment work (rails, rack mount, cable management, dedicated IPMI patch, permanent power) should happen **after GPU #3 is installed and validated**, not before, because rack-mounting around an incomplete component set just creates extra work to undo.
- Hardware safety rule for this project remains explicit: no intentional pin shorting, no guessed header operations, and no undocumented power-control steps during bring-up. Only labeled connectors, documented headers, or approved vendor tools/adapters are allowed.
- This is the first full server build in this configuration. It is expected that some parts may not fit perfectly on the first attempt and that an extra cable, bracket, adapter, or replacement part may still be needed to finish cleanly.
- Sweep system is operational and now produces daily digests, weekly rollups, follow-up queue items, and assumption-pressure checks.
- Sweep workflow now also produces a generated daily operator brief (`docs/sweeps/operator/`) so triage does not require pasting digests into chat.
- The operator brief now has basic scaling guards: recommendation line, source/entity caps, and suppression of already-triaged rows.
- The sweep scheduler was repaired on 2026-04-27 after laptop-style task settings caused missed runs and `0x800710E0` refusals; tasks now have a real working directory and `StartWhenAvailable=true`.
- X/OpenRSS source health was also recovered on 2026-04-27 by auto-enabling OpenRSS fallback when no `X_BEARER_TOKEN` exists and clearing stale X-only quarantine state.
- Release-note review now lands on `Ollama v0.23.2` as the day-one install target, matching what the official `install.sh` actually places on disk. Earlier sweeps reviewed this release as clean; the pin update simply removes the gap between the intended and actual install state.
- `vLLM` is now deliberately pinned to `v0.19.1` instead of `v0.19.0`.
- The earlier intermediate releases (`Ollama 0.22.0`, `0.22.1-rc0`, `0.23.0`) were reviewed as not strictly necessary, but the eventual move to `0.23.2` on install day made the pin discussion moot.
- Current serving posture remains: Ollama first, vLLM second, direct `llama.cpp` benchmark/watch only.
- `Qwen3.6-35B-A3B` is now logged as a future vLLM benchmark candidate, not a day-one model target.
- `Qwen3.6-Max-Preview` is now logged as a hosted proprietary coding model to watch for future routing/escalation, not a local-node target.
- `Kimi K2.6` is now logged as a serious future model-eval candidate, but it is not practical on the current 3x3090 node and is not part of the day-one local stack.
- `llm-openrouter 0.6` is now logged as future routing/fallback tooling to watch, not part of the day-one local stack.
- Sakana's `Conductor` paper is now logged as a real future orchestration signal for Nodehome: relevant to a later "manager of models" workflow layer, but not to the immediate hardware build.
- Cloudflare's new agent provisioning flow is now logged as a real future "agent-operated infrastructure" signal for Nodehome: relevant to a later orchestration/product layer, but not to the immediate hardware build.
- SubQ is now logged as a hosted long-context architecture watch item. Early access was requested on 2026-05-05; status is pending review/waitlist.
- Railway changelog #0288 is now logged as a practical agent-guardrails signal: reversible destructive actions, safer shared machine identity, and explicit deployment controls matter more as agents become operators.
- Cloudflare's agent provisioning flow with Stripe Projects is now logged as a stronger future architecture signal: agents can discover services, authorize against real user identity, spend against scoped budgets, buy domains, and deploy to production without bespoke setup.
- `llama.cpp` `b9010` is now logged as a real multi-GPU CUDA watch item for this box: it fixes PCI bus ID de-dupe behavior that could ignore other GPUs or trigger OOM conditions.
- `Ollama v0.23.0` has now been reviewed at a high level and does not currently justify moving the pinned `v0.21.2` day-one target for the Linux 3x3090 stack.
- The May 4-5 sweeps did not materially change the stack posture. Recent `llama.cpp` CUDA / multi-GPU fixes remain watch items, but no new release signal justified moving pins or changing the serving order.
- The 2026-05-05 extended sweep should be treated as lower-confidence evidence due to heavy X/OpenRSS degradation (`21` social feed failures, including `19` timeouts).
- `Ollama v0.23.2` has now also been reviewed at a high level and still does not justify moving the pinned `v0.21.2` day-one target for the Linux 3x3090 stack.
- `vLLM v0.20.2` is now on the release-review queue, but the current evidence does not justify moving the pinned `v0.19.1` helper image before baseline hardware bring-up succeeds.
- The May 8-9 sweeps did not materially change the stack posture. Recent `llama.cpp` release churn and backend-path commits remain watch items, but no new release signal justified changing the serving order.
- The workflow/social lane is currently not operator-trustworthy enough to drive decisions on its own: irrelevant Simon/Bluesky chatter is still leaking into top signals and synthesis, so infra and release items are the only reliable parts of these digests for now.

## Component Status
| Component | Price (incl tax) | Status |
|-----------|-----------------|--------|
| 3x RTX 3090 Gigabyte Turbo | $3,442 | Purchased, eBay #227287677142. **2 of 3 installed and validated** (`81:00.0` in CPU SLOT1, `C1:00.0` in CPU SLOT3, both at PCIe Gen 4 x16, full TDP power delivery confirmed under inference load). GPU #3 install blocked on one missing PCIe modular cable for the SF-1600F14HT PSU. |
| EPYC 7302P + H12SSL-i v2.0 | $985 | Arrived 2026-04-07 |
| PSU 1600W Titanium | $241 | Purchased |
| RAM 128GB DDR4-2133 ECC | $455 | Purchased, but arrived as 32GB 4DRx4 LRDIMM (`M386A4G40DM0-CPB2Q`) rather than the clean 2Rx4 RDIMM bring-up path. Open question whether the LRDIMM set is later returned or resold. |
| RAM 128GB DDR4-2400 ECC RDIMM | $428.67 | Replacement set installed and validated: all four `Samsung M393A4K40CB1-CRC4Q` sticks train, BIOS reports `Total Memory: 128 GB`. Order #26-14569-05057. |
| SSD Acer GM7 2TB | $291 | Purchased |
| SilverStone RM400 chassis | ~$260 | Purchased |
| Noctua NH-U9 TR4-SP3 cooler | $161 | Purchased from kuaka02 (Ada) |
| Noctua NF-A12x25 PWM case fan | $0 | Have it (came with rack) |
| SysRacks 24x24 server rack | $75 | Purchased |

## Budget
- **Spent (incl tax):** ~$6,339
- **Over original $5,600 budget by:** ~$739 (cooler upgrade from Arctic $70 -> Noctua $161, rack, plus replacement RDIMM purchase)
- **All components purchased and primary stack hardware now validated through POST.** The only open spend question is whether the incompatible LRDIMM set is later returned or resold.

## Blocking Issues
- No purchasing blockers other than the one missing PCIe modular cable (Super Flower SF-1600F14HT-compatible) needed to power GPU #3.
- No software version blocker. Day-one targets are now pinned Ollama `v0.23.2` (matching what is actually installed) and `vLLM v0.19.1` (vLLM not yet installed; will be staged after the third GPU is online).
- Host POST and OS install are both proved. The remaining hardware blocker is **GPU #3 power cabling**, not slot or driver capacity. Once the cable arrives, the third card slots into a free CPU PCIe 4.0 x16 (likely SLOT5 to mirror the 1/3/5 spacing pattern), and the same single-GPU validation flow that worked for #1 and #2 applies.
- Reminder: fitment surprises or a late extra order would be normal for a first-time dense rack/GPU build and should be treated as part of the learning process, not as a project failure.
- Final physical deployment (rails, rack mount, cable management, dedicated IPMI patch, permanent location in the living room) is a real remaining phase, separate from software bring-up. It is intentionally deferred until GPU #3 is installed, so the box is only handled and cabled into the rack once with the final component set.

## Known Failures
None.
