# Session Scratch - 2026-05-09 (Session 11)
Focus: OS-version decision before first installer USB is flashed.

## Observed
- Ubuntu download page now lists `26.04 LTS (Resolute Raccoon)` as the latest LTS; `24.04.4 LTS` is shown as a previous-but-supported option.
- Repo target was still `Ubuntu 24.04 LTS` across `CLAUDE.md`, `docs/architecture/software-stack.md`, `docs/HANDOVER_ASSEMBLY.md`, `docs/CURRENT_STATE.md`, and the build-guide wiki.
- User goal restated explicitly: "install once, run long-term without frequent OS upgrades."

## Decision
- Move the day-one OS target from `Ubuntu Server 24.04 LTS` to `Ubuntu Server 26.04 LTS`. Decision doc at `docs/wiki/decisions/ubuntu-26-04-over-24-04.md`.
- Reasoning summary: 26.04 adds roughly two extra years on both standard support and Pro/ESM windows compared to 24.04, avoids a future `do-release-upgrade` cycle, and the "release-day driver risk" framing does not apply to GA102 / RTX 3090 (2020-era silicon, mature in current driver branches).
- Day-one stack pins (`Ollama v0.21.2`, `vLLM v0.19.1`) are not OS-version-coupled and will be verified, not reselected, after the new install.

## Documentation deltas applied this session
- `CLAUDE.md` tech stack line now says `Ubuntu 26.04 LTS bare metal first`.
- `docs/architecture/software-stack.md` OS section now points at 26.04 (Resolute Raccoon) and references the new decision doc.
- `docs/HANDOVER_ASSEMBLY.md` checklist item updated to install 26.04.
- `docs/CURRENT_STATE.md` next-milestone language updated to 26.04 with a pointer to the decision doc.
- `docs/wiki/research/sovereign-node-build-guide.md` section 4.1 rewritten for 26.04, with 24.04 retained as a documented fallback.
- New decision file `docs/wiki/decisions/ubuntu-26-04-over-24-04.md`.
- New `docs/SESSION_LOG.md` Session 11 entry recording the decision.

## Not Proved (still ahead of the build)
- Working bootloader on `BLK0`.
- Installed OS reachable from the BMC console after reboot.
- Any GPU-populated state (still at minimum CPU + RAM + NVMe).
- Any benchmark, CUDA, or model-load behavior.

## Next physical step
- On Windows: download `Ubuntu Server 26.04 LTS` ISO, verify SHA256, flash with Rufus using GPT / UEFI (non-CSM) / ISO Image mode.
- On the server: boot the USB via the F11 boot menu, pick the entry starting with `UEFI:`.
- Pause at the GRUB menu (`Try or Install Ubuntu Server`) and confirm before running the installer prompts.
