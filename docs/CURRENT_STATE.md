# Current State

**Last Updated:** 2026-05-09

## Active Work
- Hardware bring-up has now passed POST. The board reaches the Aptio BIOS setup utility on a `Supermicro H12SSL-i` running BIOS `3.3` / build `03/28/2025` / CPLD `F0.A6.47`, boot mode is `UEFI` with LEGACY disabled, and `IPMI STATUS: Working` at BMC firmware revision `01.05.02` is shown on the IPMI tab.
- All four replacement RDIMMs (`Samsung M393A4K40CB1-CRC4Q`) have trained: BIOS Main now reports `Total Memory: 128 GB`. The earlier `32 GB` BIOS readout was from a 1-DIMM minimum-config session and is no longer current.
- Storage is enumerated at the firmware level but no OS is installed yet: the EFI shell `map -r` lists exactly one block device, `BLK0` at `PciRoot(0x0)/Pci(0x3,0x3)/Pci(0x0,0x0)/NVMe(0x1,...)`, with no `FS0:` filesystem alias. SATA0-15 across both onboard controllers are reported `Not Present`, which matches the diskless-SATA build.
- Repo-truth hardware limit: photo evidence has now been verified for POST, BMC, IPMI, NVMe enumeration, and the 4-DIMM training claim. What is **not** yet proved from durable evidence is a working OS install, a working bootloader on `BLK0`, or any GPU-populated state — those remain ahead of the build, not behind it.
- The next physical milestone is: boot a UEFI Ubuntu Server 24.04 installer USB, install onto `BLK0`, verify reboot from NVMe, then move into controlled OS bring-up before single-GPU validation.
- Known BIOS tuning item to revisit after first Ubuntu boot: `Re-Size BAR Support` is currently `[Disabled]` while `Above 4G Decoding` is `[Enabled]`. ReBAR is the natural pairing for 3x RTX 3090 inference and should be A/B tested as a deliberate change after baseline boot, not flipped blind.
- Hardware safety rule for this project remains explicit: no intentional pin shorting, no guessed header operations, and no undocumented power-control steps during bring-up. Only labeled connectors, documented headers, or approved vendor tools/adapters are allowed.
- This is the first full server build in this configuration. It is expected that some parts may not fit perfectly on the first attempt and that an extra cable, bracket, adapter, or replacement part may still be needed to finish cleanly.
- Sweep system is operational and now produces daily digests, weekly rollups, follow-up queue items, and assumption-pressure checks.
- Sweep workflow now also produces a generated daily operator brief (`docs/sweeps/operator/`) so triage does not require pasting digests into chat.
- The operator brief now has basic scaling guards: recommendation line, source/entity caps, and suppression of already-triaged rows.
- The sweep scheduler was repaired on 2026-04-27 after laptop-style task settings caused missed runs and `0x800710E0` refusals; tasks now have a real working directory and `StartWhenAvailable=true`.
- X/OpenRSS source health was also recovered on 2026-04-27 by auto-enabling OpenRSS fallback when no `X_BEARER_TOKEN` exists and clearing stale X-only quarantine state.
- Release-note review remains resolved in favor of `Ollama v0.21.2` for day-one install, and the bootstrap now pins that version explicitly instead of following latest stable.
- `vLLM` is now deliberately pinned to `v0.19.1` instead of `v0.19.0`.
- `Ollama 0.22.0` / `0.22.1-rc0` now pressure the target again, but current evidence says they are mostly new-model / MLX / launch changes rather than Linux RTX 3090 must-haves, so the pin stays at `0.21.2` for now.
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
| 3x RTX 3090 Gigabyte Turbo | $3,442 | Purchased, eBay #227287677142 |
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
- No purchasing blockers.
- No software version blocker. Current day-one targets are pinned Ollama `v0.21.2` and `vLLM v0.19.1`.
- Host POST is now proved. The next blocker is OS install: boot a UEFI Ubuntu Server 24.04 installer USB, install onto `BLK0`, then verify reboot from NVMe before any GPU population.
- Reminder: fitment surprises or a late extra order would be normal for a first-time dense rack/GPU build and should be treated as part of the learning process, not as a project failure.

## Known Failures
None.
