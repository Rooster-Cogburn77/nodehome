# Sovereign Node v1.0 - Build & Configuration Guide

**Last Updated:** 2026-04-05
**Status:** Research compilation from web sources, needs hands-on validation

---

## Table of Contents
1. [Supermicro H12SSL-i Motherboard](#1-supermicro-h12ssl-i-motherboard)
2. [SilverStone RM400 Chassis](#2-silverstone-rm400-chassis)
3. [Arctic Freezer 4U-M Cooler](#3-arctic-freezer-4u-m-cooler)
4. [Ubuntu Server + NVIDIA Drivers](#4-ubuntu-server--nvidia-drivers)
5. [Ollama / vLLM Setup](#5-ollama--vllm-setup)
6. [Stress Testing & Validation](#6-stress-testing--validation)
7. [Critical Warnings & Gotchas](#7-critical-warnings--gotchas)

---

## 1. Supermicro H12SSL-i Motherboard

### 1.1 BIOS Settings for Multi-GPU (3x RTX 3090)

**Critical BIOS settings to configure:**

| Setting | Path | Value | Why |
|---------|------|-------|-----|
| Above 4G Decoding | Advanced > PCIe/PCI/PnP Configuration | **Enabled** | Required for multi-GPU BAR allocation above 4GB boundary |
| SR-IOV Support | Advanced > PCIe/PCI/PnP Configuration | Disabled (unless doing GPU passthrough) | Only needed for virtualization |
| NUMA Nodes per Socket (NPS) | Advanced > AMD CBS > DF Common Options | **NPS1** for LLM inference | NPS1 = single NUMA domain, simplest for inference workloads. NPS4 = 4 NUMA domains, better for multi-tenant but adds complexity |
| IOMMU | Advanced > AMD CBS > NBIO Common Options | **Enabled** (if doing passthrough, otherwise Auto) | Needed for PCIe device isolation |
| PCIe Speed | Advanced > PCIe/PCI/PnP Configuration | **Auto** or **Gen4** | Ensure GPUs negotiate at PCIe 4.0 |

**Sources:**
- [Supermicro FAQ on Above 4G Decoding](https://www.supermicro.org.cn/support/faqs/faq.cfm?faq=34295)
- [Supermicro H12SSL-i Manual (PDF)](https://www.supermicro.com/manuals/motherboard/EPYC7000/MNL-2314.pdf)

### 1.2 BIOS Version for EPYC 7302

The EPYC 7302 is a **7002 series (Rome)** processor. The H12SSL-i supports both 7002 and 7003 series.

- **Minimum BIOS:** Any shipping BIOS should support Rome 7002. The board was designed for this generation.
- **Recommended:** Update to the latest available BIOS from [Supermicro's firmware download center](https://www.supermicro.com/en/support/resources/downloadcenter/firmware/MBD-H12SSL-i/BIOS)
- **IMPORTANT:** BIOS V2.0+ requires BMC firmware >= V1.00.32. Update BMC **first** if below V1.00.32.
- **IMPORTANT:** After updating to BIOS R2.1 or later, you **cannot roll back** to earlier versions.

### 1.3 Known PCIe / GPU Detection Issues

Based on forum reports from real H12SSL-i users:

1. **PCIe Gen 4 negotiation failures:** Some users on the H12SSL-NT (same family) reported GPUs falling back to Gen 1/Gen 3 speeds. Fix: Update BIOS, reseat cards, try different slots. ([Linus Tech Tips thread](https://linustechtips.com/topic/1352853-supermicro-h12ssl-nt-pcie-gen-4-issues/))

2. **GPU device ordering:** With mixed GPUs, CUDA device enumeration may not match physical slot order even with `CUDA_DEVICE_ORDER=PCI_BUS_ID`. ([ServeTheHome thread](https://forums.servethehome.com/index.php?threads/supermicro-h12ssl-i-multi-gpu-build.39717/))

3. **4x 3090 power draw at 100% load:** Users reported that 4x RTX 3090s at full 350W each couldn't sustain 100% load simultaneously -- suspected PSU or power delivery issue. With 3 cards and a 1600W PSU, this should be manageable (3x350W = 1050W GPU + ~150W system = ~1200W total). ([LTT thread](https://linustechtips.com/topic/1569755-supermicro-h12ssl-i-motherboard-4x3090s-llm-training-cluster/))

4. **OS installation hangs with GPU:** Some users reported boot/install hangs with RTX 3090 as primary display. Fix: Set BIOS preferred video to **Onboard/IPMI** first, install OS via IPMI KVM, then install NVIDIA drivers. ([Proxmox forum](https://forum.proxmox.com/threads/h12ssl-i-unable-to-install-proxmox.132914/))

5. **ACS (Access Control Services):** The H12SSL-i BIOS may not expose ACS settings in an obvious location. Users have had difficulty finding it. If IOMMU groups are too broad, try moving cards to different physical slots. ([Level1Techs thread](https://forum.level1techs.com/t/supermicro-h12ssl-i-acs/202791))

6. **PCIe bifurcation:** Settings are under Advanced > PCIe/PCI/PnP Configuration. For 3x discrete GPUs in x16 slots, you do NOT need bifurcation -- bifurcation is only needed when splitting one physical slot into multiple logical devices (e.g., NVMe adapters). ([Supermicro FAQ](https://www.supermicro.com/support/faqs/faq.cfm?faq=25893))

### 1.4 PCIe Slot Layout

The H12SSL-i has **7 expansion slots** total:
- **5x PCIe 4.0 x16** slots
- **2x PCIe 4.0 x8** slots (in x16 physical)

For 3x RTX 3090 (dual-slot blower cards), use **three of the five x16 slots**, leaving one empty slot between each GPU for the dual-slot width. Slot numbering from the manual: Slots 1-7, with the specific x16 slots documented in the board layout diagram.

**PCIe-to-NUMA mapping** (from [Mete Balci's H12SSL NUMA analysis](https://metebalci.com/blog/supermicro-h12ssl-numa/)):
- Node 0 (CCD 0): Slots 5, 3
- Node 1 (CCD 1): Slots 7, 1
- Node 2 (CCD 2): Slot 6, M.2 slots, SATA 0-7
- Node 3 (CCD 3): Slot 4, Slot 2, SATA 8-15

For LLM inference with NPS1, NUMA mapping is less critical since it is all one domain.

### 1.5 IPMI/BMC Setup

The H12SSL-i uses **ASPEED AST2500 BMC** with a dedicated IPMI RJ45 port.

**Initial setup:**
1. Connect an Ethernet cable to the dedicated IPMI port (above the USB ports on the rear I/O)
2. Enter BIOS (Delete key at POST), navigate to **IPMI tab > BMC Network Configuration**
3. Choose **DHCP** or set a **Static IP**
4. Save and reboot
5. Access the BMC web interface from a browser at the assigned IP

**Default credentials:**
- Older boards: `ADMIN / ADMIN`
- Newer boards: Unique password printed on a sticker on the motherboard (often under the first M.2 slot or on the CPU cover)

**Network modes:**
- **Dedicate:** IPMI accessible only via the dedicated IPMI NIC port (recommended)
- **Share:** Accessible via NIC port-1
- **Failover:** Falls back between modes

**Fan control via IPMI:**
- The BMC controls system fans. For custom fan curves, use [smfc (Supermicro Fan Control)](https://github.com/petersulyok/smfc) or `ipmitool` commands
- **Warning:** The BMC may override fan settings to "Optimal" mode when it detects high-TDP components, overriding user-set "Standard" mode

**Sources:**
- [Boston Server IPMI How-To](https://www.boston.co.uk/blog/2022/02/09/supermicro-ipmi-how-to-series-part-one.aspx)
- [Thomas-Krenn Remote Management Guide](https://www.thomas-krenn.com/en/wiki/Remote_management_Supermicro_X12_and_H12_Motherboards)
- [Supermicro BMC/IPMI User Guide (PDF)](https://www.supermicro.com/manuals/other/BMC_Users_Guide_X12_H12.pdf)

### 1.6 Memory Configuration (4x32GB ECC RDIMM)

**Architecture:** The EPYC 7302 has **8 memory controllers**, each with **1 channel**, for a total of **8 memory channels**. The H12SSL-i has **8 DIMM slots** labeled DIMMA1 through DIMMH1 (one slot per channel).

**With 4 DIMMs in 8 slots:**
- You will be using **4 of 8 memory channels**
- This gives approximately **50-55% of maximum memory bandwidth** compared to full population
- This is a **supported but not recommended** configuration per Supermicro -- they prefer all 8 channels populated

**Which slots to populate:**
- AMD's guidance is to distribute DIMMs across channels as evenly as possible
- For 4 DIMMs, populate **every other channel** to spread across all 4 CCDs: **DIMMA1, DIMMC1, DIMME1, DIMMG1** (channels A, C, E, G)
- This gives each CCD (quadrant of the CPU) one active memory controller
- **Do NOT** put 2 DIMMs in one channel before populating other empty channels

**Performance impact:**
- For LLM inference, the primary bottleneck is GPU memory bandwidth, not CPU memory bandwidth
- 4x32GB at half bandwidth is acceptable for this workload
- If you later add 4 more 32GB sticks (filling all 8 slots = 256GB), you get full bandwidth plus more capacity for model loading/caching

**Memory specs supported:**
- DDR4-3200 ECC RDIMM (max speed with EPYC 7002)
- DDR4-2666 ECC RDIMM also supported (may be cheaper, negligible performance difference for this use case)
- **Do NOT mix** RDIMM and LRDIMM

**Sources:**
- [Thomas-Krenn: Optimization of AMD EPYC 7002 Memory Performance](https://www.thomas-krenn.com/en/wiki/Optimization_of_AMD_EPYC_7002_Rome_and_7003_Milan_working_memory_performance)
- [Level1Techs: EPYC 7002 4 vs 8 RAM sticks](https://forum.level1techs.com/t/epyc-7002-build-4-vs-8-ram-sticks/184577)
- [Supermicro H12SSL-i Manual (PDF)](https://www.supermicro.com/manuals/motherboard/EPYC7000/MNL-2314.pdf)

---

## 2. SilverStone RM400 Chassis

### 2.1 Key Specifications

| Spec | Value |
|------|-------|
| Form Factor | 4U rackmount |
| External Dimensions | 430mm W x 469mm D x 176mm H |
| Motherboard Support | SSI-CEB, ATX, mATX, Mini-ITX |
| Expansion Slots | 7x standard-profile PCI/PCIe |
| GPU Length (with 3.5" cage) | **220mm (8.6")** |
| GPU Length (cage removed) | **339mm (13.3")** |
| GPU Width | 106mm (4.2") |
| CPU Cooler Height (with card retainer) | **130mm** |
| CPU Cooler Height (without card retainer) | **148mm** |
| PSU Support | ATX/PS2 up to 160mm depth, or Mini Redundant |
| Included Fans | 1x 120mm PWM, 1x 80mm PWM |
| Drive Bays | 3x 5.25" front, plus internal 3.5" cage |

### 2.2 GPU Clearance -- CRITICAL

**RTX 3090 blower card dimensions:**
- Gigabyte RTX 3090 TURBO 24G: **266.7mm x 111.2mm x 39.8mm**
- Emtek RTX 3090 Blower: **268.6mm x 112mm x 38.5mm**

**The verdict:**
- With the 3.5" drive cage installed (220mm max): **DOES NOT FIT.** RTX 3090 blower cards are ~267mm.
- With the 3.5" drive cage **removed** (339mm max): **FITS with 70mm+ clearance.** This is the required configuration.

**You MUST remove the internal 3.5" drive cage to fit RTX 3090 blower GPUs.** This means:
- Use your NVMe SSD (Acer Predator GM7000 2TB) in the motherboard's M.2 slot -- no SATA/3.5" drives needed
- If you need additional storage, use M.2 or 2.5" drives mounted elsewhere

### 2.3 Internal Layout & Cable Routing

- GPUs mount horizontally in the standard PCIe bracket orientation (cards hang down from the motherboard)
- The 5.25" bays are at the front; the PSU mounts at the rear
- With the drive cage removed, the GPU area has clear space toward the front of the chassis
- Cable routing: Route power cables along the chassis walls, use zip ties. Keep cables away from fan intake paths
- The Super Flower Leadex Titanium 1600W PSU is 150mm deep -- fits within the 160mm PSU limit

### 2.4 Fitting 3x Dual-Slot Blower GPUs

3 dual-slot cards = 6 slots used out of 7 available. This works, but:
- Cards will be adjacent with **no gap between them** in some configurations
- Blower-style GPUs exhaust heat out the rear bracket, which is the correct design for this tight configuration
- **Do NOT use open-air cooler GPUs** -- they would recirculate hot air in the confined 4U space

### 2.5 Fan Configuration Recommendations

The stock cooling (1x 120mm + 1x 80mm) is **insufficient** for 3x 350W GPUs. Recommendations:
- Add fans to all available mounting points
- The chassis supports additional 80mm fans at the rear
- Blower GPUs are self-cooling (they pull air from inside and exhaust out the back), but they need fresh cool air intake
- Consider replacing the stock fans with high-static-pressure 120mm fans (e.g., Noctua NF-F12 iPPC 3000 PWM)
- Monitor temps closely during initial burn-in testing

**Sources:**
- [SilverStone RM400 Product Page](https://www.silverstonetek.com/en/product/info/server-nas/RM400/)
- [SilverStone RM400 Manual](https://manuals.plus/asin/B07MKSH1B8)
- [Amazon RM400 Listing](https://www.amazon.com/SilverStone-Technology-Rackmount-Chassis-SST-RM400/dp/B07MKSH1B8)

---

## 3. Arctic Freezer 4U-M Cooler

### 3.1 SP3 Socket Compatibility

**Confirmed compatible.** The Freezer 4U-M supports:
- AMD: SP3, SP6, TR4, sTRX4, sWRX8, sTR5
- Intel: LGA4189, LGA4677

The EPYC 7302 uses **Socket SP3**. This is a direct, supported socket.

### 3.2 Height Clearance -- TIGHT FIT WARNING

| Measurement | Value |
|------------|-------|
| Freezer 4U-M height | **145mm** |
| RM400 clearance (with card retainer) | 130mm |
| RM400 clearance (without card retainer) | 148mm |

**Result:** The Freezer 4U-M fits ONLY if you **remove the expansion card retainer bracket** from the RM400. This gives you 148mm of clearance vs the cooler's 145mm height -- just **3mm of margin**.

**Important considerations:**
- Without the card retainer, your 3x heavy RTX 3090 GPUs have no bracket support. You may need an aftermarket GPU support bracket or use the SilverStone [G11909520-RT expansion card holder](https://www.silverstonetek.com/en/product/info/server-nas/G11909520-RT/) that provides 15 mounting holes for different card positions
- The Freezer 4U-M Rev. 2 provides **53mm RAM clearance**, which is sufficient for standard ECC RDIMM modules (no tall heatspreaders)
- Alternative: The older **Freezer 4U SP3** is **152mm tall** and will NOT fit

### 3.3 Cooling Capacity

- Rated for CPUs up to **350W TDP**
- The EPYC 7302 is a **155W TDP** part -- the cooler is massively overkill, which means quiet operation
- Dual 120mm fans, 400-2300 RPM range
- 8 heatpipes with direct contact
- Price: ~$60-65 USD

**Sources:**
- [Arctic Freezer 4U-M Product Page](https://www.arctic.de/us/Freezer-4U-M/ACFRE00133A)
- [Phoronix Review](https://www.phoronix.com/review/arctic-freezer-4u-m)
- [Club386 Review](https://www.club386.com/arctic-freezer-4u-m-review/)
- [Noctua RM400 Compatibility](https://www.noctua.at/en/compatibility/by-components/cases/silverstone-rm400-rackmount#details)

---

## 4. Ubuntu Server + NVIDIA Drivers

### 4.1 Recommended Ubuntu Version

**Ubuntu 24.04 LTS (Noble Numbat)** is the recommended choice as of 2026:
- Long-term support until 2029 (extended to 2034 with Ubuntu Pro)
- Excellent NVIDIA driver support via apt
- Kernel 6.8+ with good EPYC/PCIe 4.0 support
- CUDA toolkit packages available in NVIDIA's official repository

Ubuntu 22.04 LTS also works but has older kernel and may require HWE kernel for optimal EPYC support.

### 4.2 NVIDIA Driver Installation (apt method -- RECOMMENDED)

**Step 1: Blacklist Nouveau (open-source driver)**
```bash
sudo tee /etc/modprobe.d/blacklist-nouveau.conf << 'EOF'
blacklist nouveau
options nouveau modeset=0
EOF
sudo update-initramfs -u
sudo reboot
```

**Step 2: Install driver via ubuntu-drivers (recommended method)**
```bash
sudo apt update
sudo apt install -y ubuntu-drivers-common
sudo ubuntu-drivers devices          # Shows detected GPUs and recommended driver
sudo ubuntu-drivers install          # Installs the recommended driver
sudo reboot
```

**Or install a specific version:**
```bash
sudo apt install -y nvidia-driver-535-server   # Enterprise/server driver
# OR
sudo apt install -y nvidia-headless-535 nvidia-utils-535   # Headless (no GUI)
```

**Step 3: Verify**
```bash
nvidia-smi                           # Should show all 3 GPUs
cat /proc/driver/nvidia/version      # Driver version
lsmod | grep nvidia                  # Kernel modules loaded
```

**apt vs .run file:**
- **apt (recommended):** Automatic DKMS rebuilds on kernel updates, easy upgrades, integrates with system package manager
- **.run file:** Manual install, breaks on kernel updates, harder to maintain. Only use if you need a very specific driver version not in the repo

### 4.3 CUDA Toolkit Installation

```bash
# Add NVIDIA's official repository
wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2404/x86_64/cuda-keyring_1.1-1_all.deb
sudo dpkg -i cuda-keyring_1.1-1_all.deb
sudo apt update

# Install CUDA toolkit
sudo apt install -y cuda-toolkit-12-6   # Or latest available version

# Set up PATH
echo 'export PATH=/usr/local/cuda/bin:$PATH' | sudo tee /etc/profile.d/cuda.sh
echo 'export LD_LIBRARY_PATH=/usr/local/cuda/lib64:$LD_LIBRARY_PATH' | sudo tee -a /etc/profile.d/cuda.sh
source /etc/profile.d/cuda.sh

# Verify
nvcc --version
```

**CUDA / Driver compatibility matrix:**
- CUDA 12.6 requires driver >= 560
- CUDA 12.3 requires driver >= 545.23
- CUDA 12.2 requires driver >= 535.54
- CUDA 12.0 requires driver >= 525.60

RTX 3090 (Ampere GA102, Compute Capability 8.6) supports CUDA 11.x through 13.x.

### 4.4 Known Issues with 3x RTX 3090 Under Linux

1. **High idle power draw:** Driver 575+ reported RTX 3090 idling at 100W+. Fix: Use `nvidia-smi -pm 1` (persistence mode) and set power limits. ([NVIDIA Forums](https://forums.developer.nvidia.com/t/575-3090-idling-at-over-100-watts/339427))

2. **Power throttling at ~300W:** Some 3090s throttle due to "SW Power Cap." Fix: Explicitly set power limit with `sudo nvidia-smi -pl 350` or limit to 280-300W for multi-GPU stability. ([NVIDIA Forums](https://forums.developer.nvidia.com/t/3090-power-throttles-around-300w/289647))

3. **Secure Boot conflicts:** NVIDIA proprietary drivers fail to load with Secure Boot enabled. Fix: Disable Secure Boot in BIOS, or sign the kernel module (more complex).

4. **Kernel update breakage:** Kernel updates can break NVIDIA drivers. Fix: DKMS handles this automatically with apt-installed drivers. After kernel update, verify with `nvidia-smi`.

### 4.5 nvidia-smi Validation Steps

After installation, run these commands to validate all 3 GPUs:

```bash
# 1. List all detected GPUs
nvidia-smi -L
# Expected: GPU 0, GPU 1, GPU 2 (all RTX 3090)

# 2. Detailed GPU info
nvidia-smi --query-gpu=index,name,uuid,memory.total,compute_cap --format=csv

# 3. Check PCIe topology
nvidia-smi topo -m
# Shows interconnection paths (PHB = through CPU, SYS = cross-socket)

# 4. Enable persistence mode (reduces init latency)
sudo nvidia-smi -pm 1

# 5. Set power limits (recommended: 280-300W for multi-GPU stability)
sudo nvidia-smi -pl 300

# 6. Monitor all GPUs in real-time
watch -n 1 "nvidia-smi --query-gpu=index,name,utilization.gpu,utilization.memory,memory.used,temperature.gpu,power.draw --format=csv"

# 7. Check PCIe link speed (see Section 6.5 for full details)
nvidia-smi --query-gpu=pcie.link.gen.current,pcie.link.width.current --format=csv
```

**Sources:**
- [NVIDIA Driver Installation - Ubuntu Server Docs](https://documentation.ubuntu.com/server/how-to/graphics/install-nvidia-drivers/)
- [OneUpTime: Install NVIDIA Drivers on Ubuntu Server](https://oneuptime.com/blog/post/2026-03-02-install-nvidia-drivers-ubuntu-server/view)
- [OneUpTime: Multi-GPU Configuration on Ubuntu](https://oneuptime.com/blog/post/2026-03-02-how-to-set-up-multi-gpu-configuration-on-ubuntu/view)
- [Puget Systems: Quad RTX3090 Power Limiting](https://www.pugetsystems.com/labs/hpc/quad-rtx3090-gpu-power-limiting-with-systemd-and-nvidia-smi-1983/)
- [nv-gpu-powerlimit-setup (GitHub)](https://github.com/dbkinghorn/nv-gpu-powerlimit-setup)

---

## 5. Ollama / vLLM Setup

### 5.1 Ollama Installation

```bash
# One-line install
curl -fsSL https://ollama.com/install.sh | sh

# Verify
ollama --version
ollama serve &    # Start the server (runs on port 11434)
```

Ollama auto-detects NVIDIA GPUs if drivers and CUDA are installed.

### 5.2 Ollama Multi-GPU Configuration (3x RTX 3090)

Ollama uses **llama.cpp** under the hood, which does **layer splitting** (pipeline parallelism), NOT tensor parallelism. Each GPU handles a subset of model layers.

**Environment variables** (set in `/etc/systemd/system/ollama.service` or shell):
```bash
# Tell Ollama to use all GPUs
export CUDA_VISIBLE_DEVICES=0,1,2

# Force all layers to GPU (prevent CPU offloading)
export OLLAMA_NUM_GPU=999

# Optional: Control VRAM split (in GB per GPU)
export OLLAMA_GPU_SPLIT=22,22,22

# Optional: Limit GPU memory fraction
export OLLAMA_GPU_MEMORY_FRACTION=0.9
```

**For systemd service:**
```bash
sudo systemctl edit ollama
# Add under [Service]:
# Environment="CUDA_VISIBLE_DEVICES=0,1,2"
# Environment="OLLAMA_NUM_GPU=999"
sudo systemctl restart ollama
```

### 5.3 Loading a 70B Quantized Model Across 3 GPUs

**VRAM budget:** 3x 24GB = 72GB total

| Quantization | 70B Model Size | Fits in 72GB? | Quality |
|-------------|---------------|---------------|---------|
| Q4_K_M | ~40GB | YES (32GB headroom) | Good for most tasks |
| Q5_K_M | ~48GB | YES (24GB headroom) | Better quality |
| Q6_K | ~57GB | YES (15GB headroom) | Near-FP16 quality |
| Q8_0 | ~70GB | BARELY (2GB headroom) | Excellent quality, tight fit |
| FP16 | ~140GB | NO | Not possible |

**Recommended:** Q6_K for best quality that fits comfortably, or Q5_K_M for more context window headroom.

```bash
# Pull and run a 70B Q6 model
ollama pull llama3.3:70b-instruct-q6_K

# Or with custom Modelfile for specific quantization
ollama run llama3.3:70b-instruct-q6_K "Hello, how are you?"
```

Ollama will automatically split the model layers across all 3 GPUs.

**Performance expectations (3x RTX 3090, PCIe 4.0):**
- Q4_K_M 70B: ~15-25 tokens/second (eval)
- Q6_K 70B: ~10-18 tokens/second (eval)
- First token latency: 1-3 seconds depending on context length
- Keep context length to 16K-32K for practical use (not 128K)

### 5.4 vLLM Installation & Setup

vLLM provides true **tensor parallelism** but has a constraint with 3 GPUs:

**IMPORTANT:** Tensor parallelism with `tp=3` only works if the model's attention head count is divisible by 3. For Llama 3 70B (64 attention heads), 64 is NOT divisible by 3. This means:
- `--tensor-parallel-size 2` works (use 2 of 3 GPUs)
- `--tensor-parallel-size 3` does NOT work for most 70B models
- Alternative: Use `--pipeline-parallel-size 3` (splits by layers, supports any count)

```bash
# Install vLLM
pip install vllm

# Run with 2-GPU tensor parallelism (leaving 1 GPU idle or for other tasks)
python -m vllm.entrypoints.openai.api_server \
  --model casperhansen/llama-3-70b-instruct-awq \
  -q awq \
  --dtype auto \
  --tensor-parallel-size 2 \
  --gpu-memory-utilization 0.90

# Or with pipeline parallelism across all 3 GPUs
python -m vllm.entrypoints.openai.api_server \
  --model meta-llama/Llama-3.3-70B-Instruct \
  --pipeline-parallel-size 3 \
  --gpu-memory-utilization 0.90
```

**vLLM vs Ollama performance:**
- vLLM with tensor parallelism: ~21 tokens/second on dual 3090 (estimated ~25+ on triple)
- Ollama (layer splitting): ~15-17 tokens/second
- vLLM is significantly faster for batch serving and high-concurrency scenarios

**Sources:**
- [vLLM Parallelism Docs](https://docs.vllm.ai/en/stable/serving/parallelism_scaling/)
- [vLLM 3 GPU Issue](https://github.com/vllm-project/vllm/issues/1208)
- [Ollama GitHub](https://github.com/ollama/ollama)
- [Multi-GPU Ollama Setup Guide](https://markaicode.com/ollama-multi-gpu-setup/)
- [vLLM with Dual RTX 3090 Guide](https://thamizhelango.medium.com/setting-up-vllm-with-dual-nvidia-rtx-3090-gpus-a-complete-guide-ab2235cef256)
- [Ahmad Osman: Don't use llama.cpp on multi-GPU](https://www.ahmadosman.com/blog/do-not-use-llama-cpp-or-ollama-on-multi-gpus-setups-use-vllm-or-exllamav2/)

### 5.5 First Model Recommendations for Testing

**Single GPU test (quick validation):**
```bash
ollama pull gemma2:2b        # 1.6GB, runs on one GPU in seconds
ollama run gemma2:2b "What is the capital of France?"
```

**Single GPU, more capable:**
```bash
ollama pull llama3.2:8b      # ~4.9GB, good general model
ollama pull mistral:7b       # ~4.1GB, strong coding
ollama pull gemma2:9b        # ~5.4GB, Google's quality model
```

**Multi-GPU test (validates layer splitting):**
```bash
ollama pull llama3.3:70b-instruct-q4_K_M   # ~40GB, needs 2+ GPUs
ollama pull deepseek-r1:70b                  # ~40GB, reasoning model
```

**Verify multi-GPU usage:**
```bash
# In one terminal, watch GPU utilization
watch -n 1 nvidia-smi

# In another terminal, run the model
ollama run llama3.3:70b-instruct-q4_K_M "Explain quantum computing"
# You should see VRAM usage across all 3 GPUs
```

---

## 6. Stress Testing & Validation

### 6.1 GPU Stress Test (gpu-burn)

```bash
# Install
git clone https://github.com/wilicc/gpu-burn
cd gpu-burn
make

# Run stress test on all GPUs for 10 minutes
./gpu_burn 600

# Run with 90% VRAM usage
./gpu_burn -m 90% 600

# Run with double precision (more thorough)
./gpu_burn -d 600

# Test specific GPU only
./gpu_burn -i 0 300   # GPU 0 for 5 minutes
```

**Healthy output looks like:**
```
GPU 0: 89.4% proc'd: 2916 (2015 Gflop/s) errors: 0 temps: 78 C
GPU 1: 91.2% proc'd: 2987 (2089 Gflop/s) errors: 0 temps: 76 C
GPU 2: 90.1% proc'd: 2945 (2051 Gflop/s) errors: 0 temps: 79 C
```

**Red flags:** Any `errors: N` where N > 0, temperature above 95C, or GPU crashes.

### 6.2 VRAM Health Check

```bash
# gpu-burn with doubles stresses VRAM more thoroughly
./gpu_burn -d -m 95% 1800    # 30-minute burn with doubles, 95% VRAM

# Check ECC errors (RTX 3090 does not have ECC, but you can check for Xid errors)
dmesg | grep -i "xid"
# Xid errors indicate GPU memory or compute errors

# NVIDIA's built-in diagnostics
nvidia-smi --query-gpu=ecc.errors.corrected.volatile.total,ecc.errors.uncorrected.volatile.total --format=csv
# Note: RTX 3090 does NOT have ECC memory, so this will show N/A
```

### 6.3 Thermal Monitoring Tools

```bash
# Real-time GPU monitoring
nvidia-smi dmon -d 1 -s putm
# p=power, u=utilization, t=temperature, m=memory

# Or use nvtop (GPU equivalent of htop)
sudo apt install nvtop
nvtop

# CPU and system temps via lm-sensors
sudo apt install lm-sensors
sudo sensors-detect    # Accept defaults
sensors                # Show all sensor readings

# Combined monitoring (split terminal with tmux)
sudo apt install tmux
tmux
# Pane 1: watch -n 1 nvidia-smi
# Pane 2: watch -n 1 sensors
# Pane 3: htop
```

### 6.4 Memtest for ECC RAM

**Method 1: GRUB menu (pre-boot)**
```
# Memtest86+ is included in Ubuntu's default GRUB menu (BIOS boot mode)
# Reboot, hold Shift to access GRUB, select "Memory test (memtest86+)"
# For UEFI: memtest86+ v6.0+ is available from Ubuntu 23.04+
```

**Method 2: Install memtest86+ manually**
```bash
sudo apt install memtest86+
sudo update-grub
# Reboot and select from GRUB menu
```

**Method 3: MemTest86 (PassMark, more features)**
- Download from [memtest86.com](https://www.memtest86.com/)
- Create bootable USB
- Boot from USB and run full test suite
- Supports ECC error detection and reporting on supported chipsets

**ECC-specific monitoring (while running):**
```bash
# Install EDAC tools
sudo apt install edac-utils
edac-util -s           # Show ECC error summary
edac-util -r           # Show ECC error report

# Or check sysfs directly
cat /sys/devices/system/edac/mc/mc*/ce_count    # Correctable errors
cat /sys/devices/system/edac/mc/mc*/ue_count    # Uncorrectable errors
```

**Recommendation:** Run memtest86+ overnight (8+ hours minimum) on first build to validate all memory is good.

### 6.5 Verify All 3 GPUs at PCIe 4.0 x16

**Method 1: nvidia-smi**
```bash
nvidia-smi --query-gpu=index,pcie.link.gen.current,pcie.link.width.current --format=csv
# Expected output:
# 0, 4, 16
# 1, 4, 16
# 2, 4, 16
# (Gen 4, Width 16 = PCIe 4.0 x16)
```

**Method 2: lspci (more detailed)**
```bash
# Find NVIDIA devices
lspci | grep -i nvidia

# Check link capabilities and status for each GPU
# Replace XX:XX.0 with actual bus IDs from above
sudo lspci -vvv -s XX:XX.0 | grep -E "LnkCap|LnkSta"

# LnkCap: Speed 16GT/s, Width x16    (capable of PCIe 4.0 x16)
# LnkSta: Speed 16GT/s, Width x16    (currently running at PCIe 4.0 x16)
```

**Speed reference:**
| PCIe Gen | Speed |
|----------|-------|
| Gen 1 | 2.5 GT/s |
| Gen 2 | 5.0 GT/s |
| Gen 3 | 8.0 GT/s |
| **Gen 4** | **16.0 GT/s** |
| Gen 5 | 32.0 GT/s |

**If a GPU shows less than Gen 4 / x16:**
1. Reseat the GPU in its slot
2. Try a different x16 slot
3. Update BIOS to latest version
4. Check for bent pins on the PCIe slot
5. Verify BIOS PCIe speed is set to "Auto" or "Gen4" (not forced to Gen3)
6. Run `sudo nvidia-smi -pm 1` -- idle GPUs may downshift PCIe link speed as a power saving measure

**Sources:**
- [Lambda Labs: GPU/CPU Stress Testing](https://lambda.ai/blog/perform-gpu-and-cpu-stress-testing-on-linux)
- [gpu-burn GitHub](https://github.com/wilicc/gpu-burn)
- [Microchip: Find PCIe Link Speed in Linux](https://support.microchip.com/s/article/How-to-find-the-PCIe-link-speed-and-width-in-Linux)
- [NVIDIA: Useful nvidia-smi Queries](https://nvidia.custhelp.com/app/answers/detail/a_id/3751)
- [MemTest86 ECC Details](https://www.memtest86.com/ecc.htm)

---

## 7. Critical Warnings & Gotchas

### 7.1 Chassis / Cooler Interference

**The Arctic Freezer 4U-M (145mm) barely fits in the RM400 (148mm without card retainer).** You have only 3mm of clearance. This means:
- You MUST remove the expansion card retainer bracket
- Consider an aftermarket GPU support bracket to secure the heavy 3090 cards
- Double-check measurements with actual hardware before committing

### 7.2 GPU Length Requires Drive Cage Removal

RTX 3090 blower cards (~267mm) exceed the RM400's default GPU clearance (220mm). **Remove the 3.5" drive cage** to get 339mm of clearance. Plan storage around M.2 NVMe only.

### 7.3 Power Budget

| Component | Watts |
|-----------|-------|
| 3x RTX 3090 @ 350W each | 1,050W |
| EPYC 7302 | 155W |
| 128GB DDR4 ECC | ~40W |
| Motherboard/fans/SSD | ~50W |
| **Total (worst case)** | **~1,295W** |
| Super Flower Leadex Titanium 1600W | 1,600W |
| **Headroom** | **~305W (19%)** |

This is workable but not generous. Consider setting GPU power limits to 280-300W each:
```bash
sudo nvidia-smi -pl 300   # All GPUs to 300W
# New total: 900 + 245 = ~1,145W (29% headroom)
# Performance impact: minimal (~5% slower inference)
```

### 7.4 vLLM Tensor Parallelism with 3 GPUs

Most 70B models have 64 attention heads, which is NOT divisible by 3. Use pipeline parallelism (`--pipeline-parallel-size 3`) instead of tensor parallelism, or use only 2 GPUs with `--tensor-parallel-size 2`.

### 7.5 Ollama vs vLLM Decision

| Factor | Ollama | vLLM |
|--------|--------|------|
| Ease of setup | Very easy (one-liner install) | Moderate (Python env) |
| Multi-GPU method | Layer splitting (pipeline) | Tensor parallelism |
| Performance (multi-GPU) | ~15-17 t/s | ~21-25 t/s |
| Model format | GGUF | HuggingFace, AWQ, GPTQ |
| API compatibility | Custom + OpenAI-compatible | OpenAI-compatible |
| Batch serving | Limited | Excellent |
| Best for | Quick testing, personal use | Production serving, max throughput |

**Recommendation:** Start with Ollama for initial testing and learning. Move to vLLM when you need maximum performance or batch serving.

### 7.6 IPMI Default Password Location

On newer H12SSL-i boards, the default BMC password is NOT `ADMIN/ADMIN`. It is printed on a sticker that may be:
- Under the first M.2 slot
- On the transparent CPU socket cover
- On the server identification tag

**Do not throw away the CPU socket cover until you have recorded this password.**

### 7.7 Boot Sequence for First Build

1. Assemble hardware outside the chassis first (breadboard test on the motherboard box)
2. Install CPU, cooler, 1 DIMM, 1 GPU only
3. Connect to IPMI via Ethernet, access BMC web interface
4. Enter BIOS, update firmware if needed (BMC first, then BIOS)
5. Configure BIOS settings (Above 4G Decoding, NPS, PCIe speed)
6. Install Ubuntu via IPMI KVM (remote console) -- do NOT rely on GPU output initially
7. Install NVIDIA drivers
8. Validate single GPU with nvidia-smi
9. Power down, add remaining 2 GPUs and 3 DIMMs
10. Boot, verify all 3 GPUs detected
11. Run stress tests (gpu-burn, memtest)
12. Install Ollama, test with small model, then 70B model
