# AI Agent Traps: Threat Model for Sovereign Node

**Last Updated:** 2026-04-04
**Source:** [raw/ai-agent-traps-deepmind-2026.md](../raw/ai-agent-traps-deepmind-2026.md)
**Paper:** Franklin et al., Google DeepMind, March 2026

## Summary
The first systematic taxonomy of how the open web can be weaponized against autonomous AI agents. Defines 6 categories of "AI Agent Traps" targeting different parts of the agent operating cycle.

## The 6 Trap Categories

| Trap | Targets | Example |
|------|---------|---------|
| **Perception** | Agent's input parsing | Hidden prompt injection in HTML/CSS invisible to humans |
| **Semantic Manipulation** | Agent's reasoning | Authoritative-sounding disinfo distorts conclusions |
| **Cognitive State** | Agent's memory (RAG/KB) | Poison a few docs in knowledge base → skewed output |
| **Behavioral Control** | Agent's actions | Manipulated email hijacks M365 Copilot, leaks context |
| **Systemic** | Multiple agents at once | Fake financial report triggers coordinated sell-off |
| **Human Supervisor** | The human operator | Agent generates misleading summaries, exploits approval fatigue |

## Direct Relevance to Sovereign Node

### Karpathy Knowledge Base Workflow
The Obsidian `raw/` → `wiki/` compilation pipeline is a textbook target for **Cognitive State Traps**. If a web-clipped article contains adversarial content, the LLM could:
- Compile poisoned information into wiki articles
- Propagate bad data through the feedback loop (query answer → new wiki entry)
- Corrupt index files that the LLM uses for navigation
- Persist across sessions since the wiki is permanent storage

**Mitigation:** Input sanitization on web-clipped content before it enters raw/. Health checks (Karpathy already suggests these) should specifically look for inconsistencies that could indicate poisoning.

### Claw-code / Local Agent Harness
Agents with tool-use (file writing, code execution, bash commands) are the highest-risk targets for **Behavioral Control Traps**. A local coding agent that can write files and execute code is powerful - and dangerous if compromised.

**Mitigation:** Sandboxed execution environments. Agent should not have unrestricted file-system access. Review-before-execute for destructive operations.

### AutoResearch (Parallel Experiments)
Running 3 parallel autoresearch streams could be vulnerable to **Systemic Traps** if all 3 agents reference the same poisoned source material.

**Mitigation:** Independent source validation across agents. Don't let all agents share the same unverified raw/ inputs.

### Human Supervisor Trap (Us)
This is the most insidious one. If the local agent generates summaries of research, and we approve actions based on those summaries without reading source material, we're vulnerable. This is literally what happened with Gemini - it generated confident summaries of market data that were fabricated, and without verification we could have acted on them.

**Mitigation:** We already have the habit of asking "level of confidence?" and verifying claims. Formalize this into the agent workflow.

## Security Principles for Sovereign Node Deployment
1. **Sanitize inputs** - Everything entering raw/ gets checked before LLM compilation
2. **Sandbox agents** - Tool-use agents operate in restricted environments
3. **Verify outputs** - Don't trust agent summaries without spot-checking sources
4. **Independent validation** - Multi-agent results cross-checked, not assumed consistent
5. **Health checks** - Regular wiki audits for inconsistencies (Karpathy's pattern)
6. **Approval hygiene** - Never rubber-stamp agent actions out of fatigue
