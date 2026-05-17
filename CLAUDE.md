# Nodehome: Sovereign Node v1.0 Bootstrap

Master instruction file for AI agents. Read this at the start of every session to restore context.

## Project Objective
Establish a private, independent AI research lab (The Sovereign Node) centered on owned hardware, local serving, and an automated research sweep/publication loop.

## Tech Stack (Current Repo Posture)
- **Motherboard:** Supermicro H12SSL-i (Rev 2.0) [PCIe 4.0, 128 Lanes]
- **CPU:** AMD EPYC 7302P (16-Core) [Purchased: $985.08 bundle]
- **RAM:** 128GB (4x32GB) Samsung HPE DDR4-2133 ECC RDIMM [Purchased: $420.00]
- **GPU Engine:** 3x Gigabyte GeForce RTX 3090 Turbo (Blower) [Purchased: $3,442.35 bundle]
- **Chassis:** SilverStone RM400 (SST-RM400) [Purchased: ~$240]
- **PSU:** Super Flower Leadex Titanium 1600W [Purchased: $223.00]
- **Cooler:** Noctua NH-U9 TR4-SP3 [Purchased: $161.29]
- **Storage:** Acer Predator GM7 2TB TLC [Purchased: $269.00]
- **Software:** Ubuntu 26.04 LTS bare metal first, Docker, Ollama, vLLM, `claw-code`
- **Virtualization:** Proxmox is not part of the day-one bootstrap; treat it as a later separate host decision

## Repository Structure
- `docs/architecture/`: System design and technical specs.
- `docs/wiki/decisions/`: Formal log of settled architectural choices.
- `docs/CURRENT_STATE.md`: Current durable snapshot of project state.
- `docs/SESSION_LOG.md`: Current-month chronological log of build progress.
- `sweeps/`: Automated research scripts for local intelligence updates.
- `site/`: Static publication site for Nodehome.

## Hard Rules (Constraints)
1. **Physical Limit:** GPUs MUST be 2-slot Blower/Turbo style. Triple-fan cards will not fit or cool correctly in the intended rack footprint.
2. **Lane Priority:** Never suggest a consumer CPU (i9/Ryzen). 128 PCIe lanes are mandatory for 3-GPU scalability.
3. **Storage Standard:** TLC NAND only. QLC is prohibited for AI server workloads.
4. **Energy Logic:** Solar/Jackery is a supplemental buffer. Idle costs are covered; heavy research happens on the grid or in peak sun.
5. **Hardware Safety:** No intentional pin shorting, no guessed header operations, and no undocumented power-control steps during bring-up.
6. **Documentation First:** Never make a major technical decision without updating the relevant durable docs and `SCRATCH.md`.
7. **Never suggest ending the session.** Do not ask "want to call the session?", "or call it a session", "good place to stop?", "ready to wrap?", "if you're done for the night", "if you have time", "fresh head tomorrow", or any variant. Do not frame recommendations around the user's energy, focus, or time of day. State what shipped, list the real next options, and let the user pick. Offering "stop" as an option is banned. The user's pace is the user's call.
8. **Never send live external communications.** No email, newsletter, post, social update, customer/subscriber message, or other external communication is authorized by default. Inference, broad instructions ("proceed", "recover", "ship", "fix", "continue"), prior-session approvals, or approval for adjacent work do not authorize a send. The default permitted action is dry-run, preview, or artifact generation only. If asking for send approval, name the exact artifact, subject/body, recipients, and send type (first send / correction / resend / addendum). If there is any ambiguity, do not send -- ask.

## Session Protocol
1. **Startup:** Read `ATTITUDE.md`, `SCRATCH.md`, `docs/CURRENT_STATE.md`, and the current `docs/SESSION_LOG.md`.
2. **During Work:** Update `SCRATCH.md` after every major technical decision.
3. **Exit:** Update `docs/CURRENT_STATE.md` and `docs/SESSION_LOG.md`.

## Reference Docs
- [Full Build BOM](docs/HANDOVER_SOURCING.md)
- [Assembly Guide](docs/HANDOVER_ASSEMBLY.md)
- [Software Stack](docs/architecture/software-stack.md)
