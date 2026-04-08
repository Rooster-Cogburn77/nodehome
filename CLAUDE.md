# Nodehome: Sovereign Node v1.0 Bootstrap

Master instruction file for AI agents. Read this at the start of every session to restore context.

## 🎯 Project Objective
Establish a private, 100% independent AI research lab (The Sovereign Node) to replace a $320/month cloud subscription tax.

## 🛠 Tech Stack (Settled)
- **Motherboard:** Supermicro H12SSL-i (Rev 2.0) [PCIe 4.0, 128 Lanes]
- **CPU:** AMD EPYC 7302P (16-Core) [Purchased: $985.08 bundle]
- **RAM:** 128GB (4x32GB) Samsung HPE DDR4-2133 ECC RDIMM [Purchased: $420.00]
- **GPU Engine:** 3x Gigabyte GeForce RTX 3090 Turbo (Blower) [Purchased: $3,442.35 bundle]
- **Chassis:** SilverStone RM400 (SST-RM400) [Purchased: ~$240]
- **PSU:** Super Flower Leadex Titanium 1600W [Purchased: $223.00]
- **Cooler:** Noctua NH-U9 TR4-SP3 [Purchased: $161.29]
- **Storage:** Acer Predator GM7 2TB TLC [Purchased: $269.00]
- **Software:** Ubuntu 24.04 LTS, Proxmox VE, Docker, Ollama, vLLM, `claw-code`

## 🏗 Repository Structure
- `docs/architecture/`: System design and technical specs.
- `docs/wiki/decisions/`: Formal log of settled architectural choices.
- `docs/SESSION_LOG.md`: Chronological log of build progress.
- `sweeps/`: Automated research scripts for local intelligence updates.
- `memory/`: Persistent operational lessons learned (in .claude/projects/).

## 🛡 Hard Rules (Constraints)
1. **Physical Limit:** GPUs MUST be 2-slot Blower/Turbo style. Triple-fan "Gamer" cards will physically not fit or will overheat in the 24x24 rack.
2. **Lane Priority:** Never suggest a consumer CPU (i9/Ryzen). 128 PCIe lanes are mandatory for 3-GPU scalability.
3. **Storage Standard:** TLC NAND only. QLC is prohibited for AI server workloads.
4. **Energy Logic:** Solar/Jackery is a supplemental buffer. Idle costs are covered; heavy research happens on the grid or in peak sun.
5. **Documentation First:** Never make a major technical decision without updating `docs/wiki/decisions/` and `SCRATCH.md`.

## 📋 Session Protocol
1. **Startup:** Read `ATTITUDE.md`, `SCRATCH.md`, and the last 2 entries of `docs/SESSION_LOG.md`.
2. **During Work:** Update `SCRATCH.md` after every major technical decision.
3. **Exit:** Update `docs/CURRENT_STATE.md` and `docs/SESSION_LOG.md`.

## 🔗 Reference Docs
- [Full Build BOM](docs/HANDOVER_SOURCING.md)
- [Assembly Guide](docs/HANDOVER_ASSEMBLY.md)
- [Software Stack](docs/architecture/software-stack.md)
