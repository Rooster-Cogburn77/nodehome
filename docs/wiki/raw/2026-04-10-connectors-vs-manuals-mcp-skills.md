# Connectors vs Manuals: MCP and Skills

- **Date Captured:** 2026-04-10
- **Source:** David Mohl
- **URL:** https://david.coffee/i-still-prefer-mcp-over-skills/
- **Status:** Captured for editorial and architecture follow-up

## Core Idea

The most useful framing in the piece is not "MCP good, skills bad." It is a cleaner split:

- `MCP` as the connector layer
- `Skills` as the manual / knowledge layer

In that model, MCP handles actual access to services and tools, while skills capture the usage patterns, gotchas, workflow rules, and context that help the model use those tools well.

## Why It Matters Here

- Good editorial angle for Nodehome:
  - `connectors vs manuals` is a strong way to explain the ecosystem without getting trapped in protocol tribalism.
- Good architectural pattern for Sovereign Node:
  - use MCP-style connectors for service/system access
  - use local skills/manuals for operator knowledge, workflow conventions, and learned gotchas
- Strong match for the existing weekly-sweep idea:
  - local inference can synthesize or package operating knowledge on top of tool access, not just replace the tool layer

## Practical Pattern Worth Stealing

When a session with a tool or MCP reveals quirks, date formats, failure modes, or best practices:

- preserve that knowledge in a reusable skill/manual
- keep the execution path in the connector/tool itself

That creates a layered pattern:

- connector for action
- manual for learned operational knowledge

## Potential Nodehome Uses

- article or note: `Connectors vs Manuals`
- editorial theme for explaining MCP, local agents, and repo-local skills
- design principle for Sovereign Node agent/tool architecture

## Follow-Up Questions

- Should Nodehome explicitly use `manuals` as the preferred term for repo-local skill-like knowledge?
- Which parts of the current stack are better treated as connectors vs manuals?
- Could weekly sweep synthesis eventually emit operator manuals or cheat sheets from repeated patterns?
