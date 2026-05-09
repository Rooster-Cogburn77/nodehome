# Session Scratch - 2026-05-09 (Session 10)
Focus: Bring-up jumped from safe bench-power to POST + BIOS + IPMI + NVMe enumeration; close the gap between repo docs and live hardware.

## Observed (verified from photo evidence cross-checked against repo)
- POST proved on `Supermicro H12SSL-i`, BIOS `3.3` / build `03/28/2025` / CPLD `F0.A6.47`.
- BMC firmware `01.05.02`, `IPMI STATUS: Working`.
- Boot mode `UEFI`, LEGACY disabled, UEFI boot order populated (UEFI Hard Disk, USB, BCM5720 PXE, EFI shell).
- EFI shell `map -r` enumerates one block device only: `BLK0` NVMe at `PciRoot(0x0)/Pci(0x3,0x3)/Pci(0x0,0x0)/NVMe(0x1,...)`. No `FS0:`.
- SATA0-15 both controllers `Not Present` (correct for this build).
- All four replacement RDIMMs (`Samsung M393A4K40CB1-CRC4Q`) trained: BIOS reports `Total Memory: 128 GB`.
- All 7 CPU PCIe 4.0 slots at OPROM `[EFI]`, bifurcation `[Auto]`. `Above 4G Decoding` `[Enabled]`. `Re-Size BAR Support` `[Disabled]`.
- Two BCM5720 NICs visible, MACs `90:5A:08:7B:73:54` and `:73:55`.

## Not Proved (still ahead of the build)
- Working bootloader on `BLK0`.
- Installed OS reachable from the BMC console after reboot.
- Any GPU-populated state (still at minimum CPU+RAM+NVMe).
- Any benchmark, CUDA, or model-load behavior.

## Decisions
- Realign repo docs to reflect the new bring-up state, do not revise `Re-Size BAR` yet — leave it `Disabled` for the baseline boot and treat ReBAR as a deliberate A/B test post-Ubuntu.
- Hold the existing `Ollama v0.21.2` / `vLLM v0.19.1` pins. Nothing in this session changes the serving stack posture.
- Keep the LRDIMM return/resale question open; it does not block bring-up now that the RDIMM set is validated.

## Next physical step
- Boot a UEFI Ubuntu Server 24.04 installer USB.
- Install onto `BLK0`.
- Verify reboot from NVMe (BIOS Boot Option `UEFI Hard Disk` should resolve to the new EFI partition on `BLK0`).
- Only after a clean reboot from NVMe, move to controlled OS bring-up and single-GPU validation.
