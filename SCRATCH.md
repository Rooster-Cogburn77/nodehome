# Session Scratch - 2026-05-09 (Session 12)
Focus: Ubuntu 26.04 install on `BLK0`, GPU #1 + GPU #2 bring-up, Ollama smoke test through real inference.

## Observed (validated this session)
- `Ubuntu Server 26.04 LTS` installed onto `BLK0` (Acer Predator GM7 2TB), kernel `Linux 7.0.0-15-generic`, hostname `homelab`, NVMe boot proven.
- Network: `eno2` UP at `192.168.1.198/24` via DHCP; SSH from workstation works; the IPMI KVM is no longer the only console.
- Drivers: `nvidia-driver-595-server-open` (LTSB + open kernel modules) at runtime `595.58.03`, CUDA `13.2`.
- GPU #1 (`81:00.0` in `CPU SLOT1`) and GPU #2 (`C1:00.0` in `CPU SLOT3`) both at `pcie.link.gen.max = 4`, `width.max = 16`. PCIe Gen 4 also confirmed under load (`gen.current` ramped `1 → 4` mid-flight).
- Power delivery: 2-cable / one-head-per-dual-head-cable config held at `348 W` (essentially 350 W TDP cap) for an 89% GPU utilization sustained inference run, no instability.
- Ollama: `v0.23.2` installed via official `install.sh`. systemd service active. Both GPUs detected by Ollama as `compute=8.6` CUDA devices, pooled `total_vram = 48 GiB`, default `num_ctx = 262144`.
- Inference end-to-end: `qwen3:8b` ran a CoT prompt and produced clean output. Larger 2000-word essay run produced the in-flight `nvidia-smi` validation snapshot.
- BMC USB virtual NIC `enxbe3af2b6059f` at `169.254.3.1/24` is harmless background — visible to the OS as an `Insyde Software / RNDIS_Ethernet_Gadget` interface, link-local only, no internet.

## Decisions made this session
- Storage layout: guided "Use entire disk" on `/dev/nvme0n1` with **LVM disabled** and **encryption off**. Reason: simpler partitioning for a headless inference server; LUKS would require a passphrase on every reboot and break unattended monthly patch cycles.
- Power cabling: use 2 separate dual-head PCIe cables per GPU, plugged into 2 separate PSU sockets, only one head of each connected to the GPU. Electrically equivalent to two single-head cables. Validated under full TDP load.
- Ollama pin: moved from `v0.21.2` to `v0.23.2` to match what the official install actually places. Already reviewed clean in prior sweeps; closes the gap between aspirational pin and real install.

## Not Proved (still ahead of the build)
- GPU #3 install — blocked on one missing PCIe modular cable for `Super Flower SF-1600F14HT`.
- Multi-GPU layer-split inference on a model that actually requires both cards (e.g., `llama3.3:70b-instruct-q4_K_M`, ~40 GB).
- vLLM install and `TENSOR_PARALLEL_SIZE=2` (or `=3` once GPU #3 is in).
- Sustained thermal validation under multi-hour load.
- ReBAR enable + A/B benchmark vs current `[Disabled]` baseline.

## Next physical step
- Source one PCIe modular cable for `SF-1600F14HT`. Acceptable sources: eBay search `"SF-1600F14HT" cable`, CableMod configurator with PSU set to Super Flower Leadex Titanium, or Super Flower USA distributor email.
- Do not substitute EVGA Supernova / Corsair Type 4 / "compatible with multiple brands" cables — Super Flower Leadex Titanium pinout is brand-specific and cross-brand mixing has documented fry incidents.

## Next software step (in flight or imminent)
- `ollama pull llama3.3:70b-instruct-q4_K_M` — ~40 GB, fits across 2x 24 GiB. Validates multi-GPU layer-split path on the existing 2-card hardware.
