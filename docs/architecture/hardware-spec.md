# Hardware Specification

## Final BOM (Bill of Materials)

| # | Component | Model | Spec | Price | Source | Status |
|---|-----------|-------|------|-------|--------|--------|
| 1 | CPU | AMD EPYC 7302 | 16C/32T, 3.0/3.3GHz, 155W | $910 (combo) | tugm4470 (eBay) | Locked |
| 2 | Motherboard | Supermicro H12SSL-i | SP3, 128 PCIe 4.0 lanes, 8 DIMM | (combo) | tugm4470 (eBay) | Locked |
| 3 | GPU 1 | Gigabyte RTX 3090 Turbo | 24GB GDDR6X, 350W, 2-slot blower | $1,060 | kuaka02 (eBay) | Locked |
| 4 | GPU 2 | Gigabyte RTX 3090 Turbo | 24GB GDDR6X, 350W, 2-slot blower | $1,060 | kuaka02 (eBay) | Locked |
| 5 | GPU 3 | Gigabyte RTX 3090 Turbo | 24GB GDDR6X, 350W, 2-slot blower | $1,060 | kuaka02 (eBay) | Locked |
| 6 | RAM | Samsung HPE 752372-081 | 128GB (4x32GB) DDR4-2133 ECC RDIMM | $420 | scwcomputers (eBay) | Purchased |
| 7 | PSU | Super Flower Leadex Titanium | 1600W, 80+ Titanium, modular | $223 | respec.io (eBay) | Locked |
| 8 | SSD | Acer Predator GM7 | 2TB NVMe, TLC NAND | $269 | eBay | Purchased |
| 9 | Chassis | SilverStone RM400 | 4U rack, short-depth | ~$240 | Amazon | Purchased |
| 10 | Cooler | Noctua NH-U9 TR4-SP3 | SP3, 125mm, dual 92mm push/pull | $150 | kuaka02 (Ada) | Purchased |
| 11 | Case Fan | Noctua NF-A12x25 PWM | 120mm rear exhaust | $0 | Bundled with rack | Have it |
| 12 | Server Rack | SysRacks 24x24 | 24" x 24" rack enclosure | $75 | — | Purchased |
| | **Total** | | | **~$5,457** | | |

## Power Budget
| Component | TDP |
|-----------|-----|
| 3x RTX 3090 | 3 x 350W = 1,050W |
| EPYC 7302 | 155W |
| RAM + SSD + Fans | ~50W |
| **Peak draw** | **~1,255W** |
| **PSU capacity** | **1,600W** |
| **Headroom** | **~345W (22%)** |

## Thermal Notes
- Blower GPUs exhaust rear, critical for 3-card density
- Noctua NH-U9 TR4-SP3: 125mm tall, 23mm clearance without card retainer, 5mm with bracket
- Noctua NF-A12x25 PWM rear exhaust supplements blower card airflow
- Blower cards create primary front-to-back airflow (~100+ CFM each)
- Under load: ~50-55 dBA from 3 blower GPUs. At idle: ~33-35 dBA (CPU cooler at 23 dBA is inaudible)
- Server lives in living room — idle noise profile matters, chose Noctua over louder Supermicro OEM

## Physical Constraints
- Chassis: 4U rack height, short depth for standard rack
- GPU slot usage: 6 of 7 expansion slots (3 x 2-slot cards)
- DIMM usage: 4 of 8 slots (expandable to 256GB)
- NVMe: 1 of available M.2 slots
