# Sovereign Node - Session Log
<!-- Current month only. Archive previous months under docs/archives/SESSION_LOG_YYYY-MM.md -->

## 2026-05-01 (Session 7)
**Focus:** Repo cleanup and repo-truth realignment
**What was done:**
- Re-read the current repo state with zero trust toward prior handoff claims.
- Confirmed the worktree is still clean except for two untracked root files: `Home Build Progress Tracking doc_notes.docx` and its Word lockfile.
- Confirmed the latest verified repo commit remains `87a04c5`.
- Realigned stale docs that contradicted newer repo truth:
  - `CLAUDE.md` no longer lists Proxmox as part of the settled day-one stack.
  - `docs/CURRENT_STATE.md` now reflects the later safe bench-power checkpoint already recorded in the April log, while explicitly preserving that current in-chassis state and successful POST are still unproved from repo evidence.
  - `docs/HANDOVER_ASSEMBLY.md` now matches the newer serving posture: TP=3 is a validation target, not a universal guarantee or a blanket impossibility.
  - `SCRATCH.md` was reset to the current session and now records the cleanup scope and evidence boundary.
- Archived April session history into `docs/archives/SESSION_LOG_2026-04.md` and started a May log per the repo's own documentation-architecture rule.
- Added a narrow `.gitignore` rule for Word lockfiles (`~$*.docx`) without ignoring the actual untracked `.docx` note file.
**Commits:** Pending
**Next:** Verify the diff, then decide whether to leave the untracked `.docx` note outside git, add a repo-specific ignore for it, or remove it manually if it is no longer needed.

## 2026-05-05 (Session 8)
**Focus:** Hyperscaler capex recall and SubQ watch-state
**What was done:**
- Recovered the saved hyperscaler capex summary from the local wiki: `~$600B+/year` in 2026 and `~$1.3T` over 2024-2026, with the caveat that the repo stored a rolled-up conclusion rather than a filing-by-filing table.
- Re-checked the historical infrastructure comparison framing and corrected the old Interstate shorthand: the stored `~2x Interstate` line does not hold up cleanly and should be treated as stale until rebuilt with a single inflation-consistent table.
- Reviewed SubQ from primary vendor materials and classified it as a hosted long-context architecture watch item: interesting enough to track, but not a current local-node stack input.
- Logged that early access for SubQ was requested and that the current status is pending review/waitlist.
- Reviewed Railway changelog #0288 and logged it as an agent-guardrails signal rather than a Railway-only product note: reversible destructive actions, workspace/shared machine identity, and explicit deploy controls all map directly onto safer agent-operated infrastructure design.
- Reviewed the actual `Ollama v0.23.0` release notes and confirmed they are mostly Claude Desktop launch integration, app recommendations, Windows OpenClaw timeout fixes, and Metal hardening. Conclusion: not enough to move the pinned Linux 3x3090 target off `v0.21.2`.
- Reviewed `llama.cpp b9010` and confirmed it fixes CUDA PCI bus ID de-dupe behavior that could ignore additional GPUs or trigger OOM conditions. Conclusion: real multi-GPU watch item for this box.
- Reviewed the 2026-05-04 and 2026-05-05 sweep cluster and concluded there was no major new stack signal: recent `llama.cpp` CUDA / multi-GPU fixes remain watch items, but no new Ollama/vLLM/serving change justified moving pins or changing the current serving order.
- Noted that the 2026-05-05 extended run is low-confidence due to source-health degradation (`21` social feed failures, including `19` timeouts), so that digest should not be treated as strong evidence.
- Reviewed Cloudflare's `Agents can now create Cloudflare accounts, buy domains, and deploy` post and logged it as a high-signal future architecture note: the important pattern is not Cloudflare specifically, but agent-operated infrastructure built around discovery, authorization, payment, scoped budgets, and production deployment with humans only at approval boundaries.
**Commits:** Pending
**Next:** If needed, replace the old hyperscaler historical comparison note with a clean inflation-consistent table and keep SubQ in the hosted-routing watch lane until independent validation improves.

## 2026-05-09 (Session 12)
**Focus:** Ubuntu 26.04 install on `BLK0`, single- and dual-GPU bring-up, Ollama smoke test
**What was done:**
- Flashed an Ubuntu Server 26.04 LTS installer USB on Windows via Rufus (GPT, UEFI non-CSM, ISO Image mode), with SHA256 of the ISO verified against `releases.ubuntu.com/26.04/SHA256SUMS` (`dec49008a71f6098d0bcfc822021f4d042d5f2db279e4d75bdd981304f1ca5d9`).
- Booted the installer on the H12SSL-i via the F11 boot menu, took the explicit `UEFI:` USB entry, and walked the Subiquity prompts. Storage layout was guided "Use entire disk" on the Acer Predator GM7 with **LVM disabled** and **encryption off** (rationale: simpler partitioning for a headless inference server, and LUKS would require a passphrase on every reboot which is incompatible with unattended monthly patch reboots). SSH server was enabled on install.
- Identified an installer-time gotcha: the only interface initially showing an IP was `enxbe3af2b6059f` at `169.254.3.1/24`, which is the BMC's `Insyde Software / RNDIS_Ethernet_Gadget` USB virtual NIC and has **no real internet access**. Plugging an ethernet cable into one of the rear LAN1/LAN2 ports brought `eno2` up properly with a real `192.168.1.198/24` DHCP lease. Logged this so the next install does not waste time on the same trap.
- Confirmed first-boot OS health on the installed system: kernel `Linux 7.0.0-15-generic`, hostname `homelab`, `lsblk` shows `/boot/efi` + `/` partitions on `nvme0n1`, `free -h` shows ~123 GiB usable from 128 GiB physical (normal kernel/firmware reservation), `smartctl -i` confirms the NVMe is in fact the `Predator SSD GM7 2TB` (the lspci-side `Biwin / HP FX700` string is just an outdated PCI ID database label and is not authoritative).
- Patched the OS (`apt update && apt upgrade -y`) and rebooted cleanly before adding GPUs, so the OS baseline is a fully-patched 26.04.0 install with no known-vulnerable packages.
- Installed GPU #1 in `CPU SLOT1` (the primary PCIe 4.0 x16). The card enumerated as `81:00.0` (GA102 / RTX 3090) plus its companion HDMI audio function. Pre-driver `lspci -vv LnkSta` showed `Speed 2.5GT/s (downgraded), Width x16` — consistent with idle ASPM downclock pre-driver, not a real Gen 4 negotiation failure (`LnkCap` already showed `16 GT/s, x16`).
- Installed `nvidia-driver-595-server-open` (LTSB branch + open kernel modules) via `ubuntu-drivers`. After reboot, `nvidia-smi` showed `Driver Version: 595.58.03`, `CUDA Version: 13.2`, GPU 0 idle at `36 C / 11 W / P8`.
- Confirmed PCIe Gen 4 capability with `nvidia-smi --query-gpu=pcie.link.gen.max,pcie.link.width.max --format=csv` returning `4, 16` for both current and max — the H12SSL-i Gen 4 negotiation issue flagged in the build-guide wiki is **not** affecting this build.
- Discussed PCIe power cabling: original plan called for two single-head PCIe cables per GPU. Available cables are dual-head, but the user proposed using one head from each of two separate cables (drawn from two separate PSU modular sockets), which is electrically identical to the two-single-head plan. That configuration was used for both GPUs.
- Installed GPU #2 in `CPU SLOT3`. Enumerated as `C1:00.0`. `nvidia-smi --query-gpu=index,pci.bus_id,pcie.link.gen.max,pcie.link.width.max --format=csv` confirmed both GPUs at `gen.max = 4`, `width.max = 16`. SLOT3 trained cleanly.
- Installed Ollama via the official `install.sh`. The script pulled `v0.23.2` (latest stable, previously reviewed clean in earlier sweeps). The systemd service started cleanly and Ollama auto-detected both GPUs as `library=CUDA compute=8.6` devices, pooled `total_vram=48.0 GiB`, and set a default context window of `262144` tokens (256K).
- Pulled `qwen3:8b` (~5.2 GB, single GPU footprint), ran a chain-of-thought prompt, captured clean output.
- Captured the in-flight `nvidia-smi` snapshot during a longer 2000-word essay generation. GPU 0 showed `pcie.link.gen.current = 4`, `memory.used = 10942 MiB`, `utilization.gpu = 89%`, `power.draw = 348.48 W` — all four of the validations we wanted in one snapshot. PCIe Gen 4 confirmed in practice, not just on paper. Power delivery from the dual-head-one-head cable configuration held cleanly at the 350 W TDP cap.
- Logged `Super Flower SF-1600F14HT` (Leadex 80+ Titanium 1600W) as the PSU model that drives cable sourcing for GPU #3, and recorded the explicit warning that EVGA Supernova / Corsair Type 4 / generic "compatible" cables must not be used — even where the same OEM (Super Flower) made the EVGA internals, the modular-socket pinouts differ and cross-brand mixing has well-documented fry incidents.
- Updated `docs/CURRENT_STATE.md`, `docs/architecture/software-stack.md`, and component status to reflect: OS installed and patched, 2 GPUs validated end-to-end through inference, Ollama pin moved from `v0.21.2` to `v0.23.2` to match the actual install, and remaining work scoped to "1 cable + 1 GPU + bigger model validation."
**Commits:** Pending
**Next:** Source the PCIe modular cable for the SF-1600F14HT and stage the third GPU in CPU SLOT5. While that ships, pull `llama3.3:70b-instruct-q4_K_M` (~40 GB) to validate multi-GPU layer-split inference on the existing 2-card configuration, since 70B Q4 fits cleanly across 2x 24 GiB.

## 2026-05-09 (Session 11)
**Focus:** OS-version decision before first installer USB is flashed
**What was done:**
- Recognized that the `Ubuntu 24.04 LTS` target encoded across the repo predated the current Ubuntu download page, where `26.04 LTS (Resolute Raccoon)` is now the latest LTS and `24.04.4 LTS` is offered as a previous-but-supported option.
- Re-evaluated the choice against the user's stated goal of "install once, run long-term without frequent OS upgrades." Concluded that 26.04 is the better target because it adds roughly two extra years of standard support and two extra years of Pro/ESM support over 24.04, and avoids a future `do-release-upgrade` cycle entirely.
- Verified that the "26.04 is brand-new" risk does not meaningfully apply to RTX 3090: GA102 / Ampere is 2020-era silicon, fully covered by current NVIDIA proprietary driver branches.
- Updated the day-one stack target across the repo: `CLAUDE.md`, `docs/architecture/software-stack.md`, `docs/HANDOVER_ASSEMBLY.md`, `docs/CURRENT_STATE.md`, and `docs/wiki/research/sovereign-node-build-guide.md`.
- Added a formal decision doc at `docs/wiki/decisions/ubuntu-26-04-over-24-04.md` recording the rationale, the alternatives considered, and a documented rollback path to 24.04.4 LTS if a 26.04-specific bring-up blocker appears.
- Confirmed posture on day-one stack pins: `Ollama v0.21.2` and `vLLM v0.19.1` are userspace and not OS-version-coupled. Treat their relationship to 26.04 as verification after install, not re-architecture.
**Commits:** Pending
**Next:** Flash the Ubuntu Server 26.04 LTS installer USB on Windows via Rufus (GPT, UEFI non-CSM, ISO mode), then boot it on the H12SSL-i and pause at the GRUB menu before running the installer prompts.

## 2026-05-09 (Session 10)
**Focus:** Bring-up jumped from safe bench-power to POST + BIOS + IPMI + NVMe enumeration
**What was done:**
- Verified the prior repo-truth claim ("POST not proved") against fresh photo evidence and concluded it is now stale. The `Supermicro H12SSL-i` reaches the Aptio BIOS setup utility on BIOS `3.3` / build `03/28/2025` / CPLD `F0.A6.47`, with Memory Information populated and the standard tab set rendering.
- Confirmed BMC and IPMI directly: IPMI tab shows `BMC Firmware Revision 01.05.02` and `IPMI STATUS: Working`, with `System Event Log` and `BMC Network Configuration` available.
- Confirmed boot mode is `UEFI` with `LEGACY to EFI Support: Disabled` and a fixed UEFI boot order including `UEFI Hard Disk`, USB classes, the dual `Broadcom NetXtreme BCM5720` NICs (MACs `90:5A:08:7B:73:54` and `:73:55`), and the built-in EFI shell.
- Confirmed NVMe enumeration at firmware level: EFI shell `map -r` shows exactly one block device, `BLK0` at `PciRoot(0x0)/Pci(0x3,0x3)/Pci(0x0,0x0)/NVMe(0x1,...)`, with no `FS0:` filesystem alias. SATA0-15 across both onboard controllers (`B:48` and `B:49`) report `Not Present`, which matches the diskless-SATA build.
- Validated the replacement RDIMM purchase: with all four `Samsung M393A4K40CB1-CRC4Q` sticks installed, BIOS Main now reports `Total Memory: 128 GB`. The earlier `32 GB` BIOS readout from a 1-DIMM minimum-config session is no longer current and should not be cited as live state.
- Confirmed PCIe posture for later GPU validation: all 7 CPU PCIe 4.0 slots are set to OPROM `[EFI]` with bifurcation `[Auto]`, `Above 4G Decoding` is `[Enabled]`. Logged `Re-Size BAR Support: [Disabled]` as a known future BIOS tuning item to revisit as a deliberate A/B test after baseline Ubuntu boot, not before.
- Realigned `docs/architecture/overview.md` so the physical-layer ASCII diagram shows `Noctua NH-U9 TR4-SP3` instead of the obsolete `Arctic Freezer 4U-M`. Other architecture docs already reflected Noctua.
- Updated `docs/CURRENT_STATE.md` to record POST proved, IPMI working, NVMe enumerated, 128GB trained, and the new milestone of installing Ubuntu Server 24.04 onto `BLK0`.
**Commits:** Pending
**Next:** Boot a UEFI Ubuntu Server 24.04 installer USB, install onto `BLK0`, verify reboot from NVMe, then move into controlled OS bring-up before single-GPU validation.

## 2026-05-09 (Session 9)
**Focus:** May 8-9 sweep triage and corrected bring-up RAM path
**What was done:**
- Reviewed the 2026-05-08 core/extended and 2026-05-09 core sweeps for operator-relevant signal instead of treating the generated synthesis as trustworthy by default.
- Logged the only immediate stack-relevant release pressure from that cluster: `Ollama v0.23.2` and `vLLM v0.20.2` are now known review items, but current evidence still does not justify moving the pinned `Ollama v0.21.2` and `vLLM v0.19.1` targets before baseline hardware bring-up succeeds.
- Kept the `llama.cpp` build churn (`b9070-b9089`) and recent backend commits in the benchmark/watch lane only; no May 8-9 release signal changed the `Ollama -> vLLM -> direct llama.cpp benchmark` serving order.
- Logged that the workflow/social lane is currently not operator-trustworthy enough to drive decisions on its own: irrelevant Simon/Bluesky chatter is still leaking into top signals and synthesis, so the infra/release lane is the only reliable part of these digests for now.
- Corrected the memory diagnosis by checking the physical DIMM labels instead of relying on stale IPMI inventory: the original 128GB set is `32GB 4DRx4 LRDIMM` (`Samsung M386A4G40DM0-CPB2Q`), not the clean `2Rx4 RDIMM` path required for an unambiguous bring-up test.
- Purchased a replacement 128GB RDIMM set for proof testing: `4x Samsung M393A4K40CB1-CRC4Q`, eBay order `#26-14569-05057`, total paid `$428.67`, expected delivery `2026-05-07` to `2026-05-11`.
- Updated `docs/CURRENT_STATE.md` so the repo snapshot now reflects the May 8-9 sweep posture and the corrected bring-up RAM status.
**Commits:** Pending
**Next:** When the replacement RDIMMs arrive, retest in minimum config with `1` new stick in `DIMMA1` before adding GPUs or touching the pre-seated CPU.
