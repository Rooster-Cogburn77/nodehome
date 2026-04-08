# Sovereign Node v1.0 - System Architecture

## Physical Layer
```
┌─────────────────────────────────────────────────────────┐
│  SilverStone RM400 (Short-Depth 4U Rack Chassis)        │
│                                                         │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐                 │
│  │ RTX 3090│  │ RTX 3090│  │ RTX 3090│  ← 3x Blower    │
│  │ 24GB    │  │ 24GB    │  │ 24GB    │    2-slot each   │
│  │ Gigabyte│  │ Gigabyte│  │ Gigabyte│                   │
│  │ Turbo   │  │ Turbo   │  │ Turbo   │                   │
│  └────┬────┘  └────┬────┘  └────┬────┘                   │
│       │ PCIe 4.0   │ x16       │ x16                    │
│  ┌────┴────────────┴───────────┴────┐                   │
│  │  Supermicro H12SSL-i             │                   │
│  │  AMD EPYC 7302 (16C/32T)        │                   │
│  │  128 PCIe 4.0 lanes             │                   │
│  │  8x DIMM slots                  │                   │
│  │  [32GB][32GB][32GB][32GB][ ][ ][ ][ ] ← 128GB ECC   │
│  └──────────────────────────────────┘                   │
│                                                         │
│  [Acer GM7 2TB NVMe]  [Arctic Freezer 4U-M]            │
│                                                         │
│  [Super Flower Leadex Titanium 1600W PSU]               │
└─────────────────────────────────────────────────────────┘
```

## VRAM Topology
- **Total VRAM:** 72GB (3x 24GB)
- **Per-GPU bandwidth:** 936 GB/s
- **Interconnect:** PCIe 4.0 x16 (no NVLink - tensor parallelism will be slower than NVLink-connected GPUs)
- **Model distribution:** Pipeline parallelism across GPUs (model layers split across cards)

## Use Cases (Planned)

### Primary: LLM Inference
- 70B models at Q6-Q8 quantization across 3 GPUs
- 26B models (Gemma 4 MoE) on single GPU for fast responses
- Multi-model swarm: different models on each GPU simultaneously

### Secondary: Research
- Karpathy AutoResearch (parallel experiments across GPUs)
- Knowledge base workflow (Obsidian + LLM compilation)
- Fine-tuning small models (LoRA on single GPU)

### Future: Upgrade Path
- Swap 3090s for A100 40GB/80GB when ITAD prices drop
- Add more RAM (8 DIMM slots, only 4 populated)
- Second NVMe for data storage
