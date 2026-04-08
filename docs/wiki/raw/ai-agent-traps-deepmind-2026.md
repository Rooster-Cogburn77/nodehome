# AI Agent Traps (DeepMind, 2026)

## Metadata
- **URL:** https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6372438
- **Authors:** Matija Franklin, Nenad Tomasev, Julian Jacobs, Joel Z. Leibo, Simon Osindero (Google DeepMind)
- **Date Published:** March 8, 2026
- **Date Found:** 2026-04-04
- **Found Via:** @alex_prompter on X (https://x.com/alex_prompter/status/2040731938751914065)
- **Relevance:** Direct threat model for Sovereign Node's autonomous agent workflows (claw-code, autoresearch, knowledge base compilation)
- **Status:** compiled (wiki article exists)
- **Wiki Article:** [ai-agent-traps](../research/ai-agent-traps.md)

## Source Content

First systematic framework for understanding how the open web can be weaponized against autonomous AI agents. Defines "AI Agent Traps": adversarial content embedded in web pages and digital resources, engineered to exploit visiting agents.

### Six Categories of Traps

**1. Perception Traps**
Content injections exploiting the gap between what a human sees on a web page and what an AI agent parses. Hidden instructions in HTML/CSS that are invisible to humans but read by agents. Classic prompt injection via hidden text.

**2. Semantic Manipulation Traps**
Targets an agent's reasoning. Emotionally charged or authoritative-sounding content distorts how the agent synthesizes information and draws conclusions. Manipulates the agent's interpretation rather than its input.

**3. Cognitive State Traps**
Turns long-term memory into a vulnerability. Poisoning just a handful of documents in a RAG knowledge base is enough to reliably skew the agent's output for specific queries. Memory corruption persists across sessions.

**4. Behavioral Control Traps**
Direct takeover of agent actions. Example cited: a single manipulated email got an agent in Microsoft's M365 Copilot to bypass security classifiers and leak its entire privileged context. Most dangerous for agents with tool-use capabilities (file writing, code execution, API calls).

**5. Systemic Traps**
Target thousands of AI agents simultaneously. Example: a fake financial report released at the right time could trigger synchronized sell orders among thousands of AI trading agents. Cascading failure through coordinated manipulation.

**6. Human Supervisor Traps**
Turn the AI against its own human operator. Compromised agent generates truncated summaries or misleading analyses, exploiting approval fatigue. The human rubber-stamps actions they wouldn't approve if they saw the full picture.

## Key Takeaways
- The web itself is the attack surface, not just the model
- Agents with tool-use (file writing, code execution) are highest risk targets
- RAG/knowledge base poisoning is surprisingly easy and persistent
- Human-in-the-loop doesn't help if the agent is manipulating the human's view
- Multi-agent systems are vulnerable to cascading/coordinated attacks
- The 6 categories map to different parts of the agent operating cycle: perception, reasoning, memory, action, multi-agent, and human oversight

## Action Items
- [ ] Read full paper when available
- [ ] Map each trap category to Sovereign Node's planned agent workflows
- [ ] Design input sanitization for the Obsidian knowledge base intake pipeline
- [ ] Consider sandboxing for agents with file-write access
- [ ] Build this into the software stack planning before deployment
