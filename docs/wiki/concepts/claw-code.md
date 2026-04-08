# Claw-code: Open-Source Claude Code Agent Harness

**Last Updated:** 2026-04-04

## What It Is
Claw-code is a legitimate open-source clean-room rewrite of Claude Code's agent harness.
- **Repo:** github.com/instructkr/claw-code
- **Purpose:** Provides the orchestration layer that lets an LLM operate as a coding agent (file reading, editing, command execution, tool use)
- **Status:** Active open-source project

## Why It Matters
Claude Code (what you're using right now) is Anthropic's proprietary CLI. Claw-code replicates the agent behavior pattern so you can:
- Run it with local models on the Sovereign Node
- Modify the agent behavior for custom workflows
- Not depend on Anthropic's cloud API for the agent harness itself

## Misconception Corrected
Initially flagged as potentially pirated software. User corrected this - it's a legitimate clean-room rewrite, not stolen code. Verified via GitHub and DeepWiki. The lesson: verify before assuming, especially for open-source projects with names that reference commercial products.

## Planned Use
Run claw-code locally on the Sovereign Node with Gemma 4 or a 70B model as the backend, creating a fully local coding agent that doesn't require cloud API calls.
