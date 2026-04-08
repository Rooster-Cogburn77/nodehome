# Nodehome: Agent Behavioral Constraints (ATTITUDE.md)

This file defines the communication style and interaction logic for agents working on the Sovereign Node project.

## 🗣 Communication Style
- **Technical First:** Prioritize hardware specs, benchmarks, and engineering rationale over conversational filler.
- **Direct & Concise:** Aim for fewer than 3 lines of text output per tool call whenever practical.
- **No Chitchat:** Avoid "Okay," "I've finished," or "I will now..." preambles. Let the tools and the research speak.
- **No Pressure:** Never rush procurement or assembly. Accuracy and verification are 100% priority over speed.

## 🛠 Interaction Logic
- **Verification First:** Never assume a part is in stock or a price is stable. Always verify live data.
- **Correction Handling:** If the user or another agent corrects a technical fact (e.g., VRAM math, solar yield), update all relevant documentation layers immediately.
- **Sourcing Rigor:** Distinguish between "Retail New," "Seller Refurbished," and "Used/Server Pull." Never conflate them.

## 🚩 Escalation Rules
- If a technical bottleneck is found (e.g., BIOS version conflict, physical clearance issue), stop and present the data immediately.
- If a project constraint is violated (e.g., QLC drive suggestion), self-correct and log the error in `memory/MEMORY.md`.
