# Handover: Assembly & Deployment

## Status: IN PROGRESS
## Expires when: System running, first 70B model inference complete

**Last Updated:** 2026-04-07

---

## CRITICAL WARNINGS (Read Before Touching Hardware)

### 1. Drive Cage MUST Be Removed
RTX 3090 blower cards are ~267mm long. RM400 only allows 220mm with the 3.5" drive cage. **Remove the drive cage** to get 339mm clearance. This means NVMe-only storage (your GM7 2TB in the M.2 slot).

### 2. Card Retainer Bracket — Can Likely Keep It
Noctua NH-U9 TR4-SP3 is 125mm tall. RM400 allows 130mm with the bracket, 148mm without. **5mm clearance with bracket, 23mm without.** Try keeping the bracket first — it helps support the 3x heavy 3090s. Remove only if it interferes.

### 3. Don't Throw Away The CPU Socket Cover
The BMC/IPMI default password may be printed on it. Record it before discarding.

### 4. vLLM Tensor Parallelism Won't Work With 3 GPUs
64 attention heads on most 70B models aren't divisible by 3. Use `--pipeline-parallel-size 3` or use Ollama which handles 3 GPUs natively.

### 5. Set GPU Power Limits
Run `nvidia-smi -pl 300` after driver install. Drops from 1,050W GPU draw to 900W with ~5% performance hit. Much better thermals and power stability.

---

## Phase 1: Receiving & Inspection

### When GPUs Arrive (ETA Apr 16-28, FedEx from China)
- [ ] Inspect packaging for shipping damage
- [ ] Check all 3 cards visually: fan spins freely, no bent pins on PCIe connector, no bulging capacitors
- [ ] Verify model: Gigabyte GeForce RTX 3090 Turbo (GV-N3090TURBO-24GD)
- [ ] Note serial numbers for warranty tracking

### When Other Components Arrive
- [ ] RAM: Verify all 4 sticks present, Samsung HPE branding matches listing
- [ ] Mobo: Check socket for bent pins, verify all PCIe slots clear
- [ ] PSU: Verify all modular cables present (need 3x PCIe 8-pin pairs minimum)
- [ ] Record BMC password from CPU socket cover or sticker BEFORE discarding anything

---

## Phase 2: Breadboard Test (Outside Chassis)

Do this on the motherboard box. Validates components before you stuff them in the 4U case.

1. [ ] Install EPYC 7302 into SP3 socket (verify orientation, don't force)
2. [ ] Mount Noctua NH-U9 TR4-SP3 (SecuFirm2 SP3 mounting hardware, NT-H1 paste included)
3. [ ] Install 1x 32GB DIMM in slot **DIMMA1** only
4. [ ] Install 1x RTX 3090 in first x16 slot
5. [ ] Connect PSU: 24-pin ATX, 8-pin CPU, 1x PCIe power to GPU
6. [ ] Connect Ethernet to IPMI port
7. [ ] Power on - enter BIOS (Delete key)

### BIOS Configuration
- [ ] Update BMC firmware first if below V1.00.32
- [ ] Update BIOS to latest (cannot rollback after R2.1+)
- [ ] Enable **Above 4G Decoding** (Advanced > PCIe/PCI/PnP)
- [ ] Set **NPS to NPS1** (Advanced > AMD CBS > DF Common Options)
- [ ] Set **PCIe Speed to Auto** (Advanced > PCIe/PCI/PnP)
- [ ] Set **Preferred Video to Onboard/IPMI** (prevents boot hangs)
- [ ] Disable Secure Boot (NVIDIA drivers won't load with it on)

### Single GPU Validation
- [ ] Confirm GPU detected in BIOS
- [ ] Install Ubuntu 24.04 LTS via IPMI KVM (USB boot)
- [ ] Install NVIDIA drivers: `sudo apt install ubuntu-drivers-common && sudo ubuntu-drivers install`
- [ ] Reboot, verify: `nvidia-smi` shows 1x RTX 3090
- [ ] Check PCIe link: `nvidia-smi --query-gpu=pcie.link.gen.current,pcie.link.width.current --format=csv` → should show `4, 16`

---

## Phase 3: Full Assembly

### Chassis Prep
- [ ] Remove 3.5" drive cage from RM400
- [ ] Test fit with expansion card retainer bracket (Noctua is 125mm, bracket allows 130mm — should fit)
- [ ] Plan cable routing (PSU cables along chassis walls)

### Install Components
- [ ] Mount motherboard (already has CPU + cooler from breadboard test)
- [ ] Install all 4x 32GB DIMMs in slots: **DIMMA1, DIMMC1, DIMME1, DIMMG1** (every other channel)
- [ ] Install NVMe SSD in M.2 slot
- [ ] Mount PSU
- [ ] Install 3x RTX 3090 in x16 slots (check spacing - 6 of 7 slots used)
- [ ] Route PCIe power cables to all 3 GPUs (each needs 2x 8-pin)
- [ ] Verify card retainer bracket secures all 3 GPUs (should fit with Noctua's 125mm height)
- [ ] Mount Noctua NF-A12x25 PWM as rear exhaust fan
- [ ] Route and connect all power cables
- [ ] Mount in server rack

---

## Phase 4: Full System Validation

### Boot & BIOS Check
- [ ] Power on, enter BIOS
- [ ] Verify all 3 GPUs detected
- [ ] Verify 128GB RAM detected (4x 32GB)
- [ ] Verify NVMe SSD detected

### OS + Drivers
- [ ] Boot Ubuntu (already installed from breadboard test)
- [ ] Blacklist Nouveau: create `/etc/modprobe.d/blacklist-nouveau.conf`, `update-initramfs -u`, reboot
- [ ] Install NVIDIA driver: `sudo ubuntu-drivers install && sudo reboot`
- [ ] Verify all 3 GPUs: `nvidia-smi -L`
- [ ] Enable persistence mode: `sudo nvidia-smi -pm 1`
- [ ] Set power limits: `sudo nvidia-smi -pl 300`
- [ ] Check all GPUs at PCIe 4.0 x16:
  ```
  nvidia-smi --query-gpu=index,pcie.link.gen.current,pcie.link.width.current --format=csv
  ```
  Expected: all show `4, 16`

### Install CUDA
- [ ] Add NVIDIA repo, install cuda-toolkit
- [ ] Verify: `nvcc --version`

### Stress Tests
- [ ] **GPU burn test** (30 min all 3 GPUs):
  ```
  git clone https://github.com/wilicc/gpu-burn && cd gpu-burn && make
  ./gpu_burn -m 90% 1800
  ```
  Watch for: errors > 0, temps > 95C, crashes
- [ ] **Memtest** (overnight, 8+ hours): Boot into memtest86+ from GRUB menu
- [ ] **ECC monitoring**: `sudo apt install edac-utils && edac-util -s`
- [ ] **Thermal monitoring during burn**: `nvidia-smi dmon -d 1 -s putm`
- [ ] Install nvtop for ongoing monitoring: `sudo apt install nvtop`

---

## Phase 5: Software Stack

### Ollama (Start Here)
- [ ] Install: `curl -fsSL https://ollama.com/install.sh | sh`
- [ ] Configure multi-GPU: set `CUDA_VISIBLE_DEVICES=0,1,2` and `OLLAMA_NUM_GPU=999`
- [ ] Quick test (single GPU): `ollama pull gemma2:2b && ollama run gemma2:2b "Hello"`
- [ ] Multi-GPU layer-split experiment: `ollama pull llama3.3:70b-instruct-q4_K_M`
- [ ] Verify all 3 GPUs active: `watch -n 1 nvidia-smi` while running inference
- [ ] Test Gemma 4 26B MoE on single GPU (cognitive core candidate)
- [ ] Gemma4 FA gate: if Gemma4 crashes or produces bad output on the RTX 3090s, set `OLLAMA_FLASH_ATTENTION=0` in the Ollama systemd override and retest

### vLLM (After Ollama Baseline, For Multi-GPU Serving)
- [ ] Use the bootstrap Docker helper: `/opt/nodehome/vllm/launch_vllm.sh`
- [ ] Validate `TENSOR_PARALLEL_SIZE=3`; do not assume it works for every model
- [ ] Test CPU KV cache offload: `CPU_OFFLOAD_GB=32 /opt/nodehome/vllm/launch_vllm.sh`
- [ ] Benchmark vs Ollama on same model

### llama.cpp Direct (Watch / Benchmark Only)
- [ ] Track tensor/split-mode changes from the sweep notebook
- [ ] Do not make direct llama.cpp tensor/split-mode a day-one serving dependency while upstream marks it experimental

### Ollama vs vLLM Quick Reference
| | Ollama | vLLM |
|--|--------|------|
| Setup | One-liner | Python env |
| 3-GPU method | Layer splitting experiments | TP=3 validation target; model-dependent |
| Speed | ~15-17 t/s | ~21-25 t/s |
| Best for | First inference, convenience, small/single-GPU models | Multi-GPU serving experiments, throughput |

---

## Phase 6: Knowledge Base Setup

### Obsidian + Karpathy Workflow
- [ ] Install Obsidian (can run on a separate machine, vault on shared storage or synced folder)
- [ ] Set up vault structure: `raw/`, `wiki/`, matching our existing docs/wiki/ layout
- [ ] Install Obsidian Web Clipper extension
- [ ] Test the pipeline: clip an article → raw/ → LLM compiles wiki article → indexes updated

### Claw-code (Local Agent Harness)
- [ ] Clone: `git clone https://github.com/instructkr/claw-code`
- [ ] Configure to use local Ollama endpoint
- [ ] Test with Gemma 4 26B as backend

### AutoResearch (Karpathy)
- [ ] Clone: `git clone https://github.com/karpathy/autoresearch`
- [ ] Configure for single-GPU experiments
- [ ] Test with a simple research prompt

---

## Phase 7: Ongoing Operations

### Daily
- Monitor thermals: `nvtop`
- Check for Xid errors: `dmesg | grep -i xid`

### Weekly
- Check ECC status: `edac-util -s`
- Verify all GPUs still at PCIe 4.0 x16

### When Fans Get Loud/Grinding
- Blower fan bearing is first failure point (3-7 year lifespan)
- Replacement fans: ~$15-25, 15 minutes to swap
- Repaste thermal compound every 2-3 years

---

## Detailed Technical Reference
See [docs/wiki/research/sovereign-node-build-guide.md](wiki/research/sovereign-node-build-guide.md) for:
- Complete BIOS settings table
- PCIe slot layout and NUMA mapping
- DIMM slot population order
- Full nvidia-smi validation commands
- CUDA/driver compatibility matrix
- All source links and forum references
