# Nodechat Scope

Status: authoritative scope and product philosophy for `scripts/nodechat.py`. Operational/usage details live in [`nodechat-terminal.md`](nodechat-terminal.md).

## What Nodechat Is

Nodechat is the local agentic terminal environment for Nodehome.

It is not a limited chat wrapper. It is intended to combine model reasoning, private AI History, current repo state, live node state, command execution, filesystem operations, internet research, provenance, and durable audit into one terminal workflow.

The product philosophy is **capability with evidence, not restriction by default.** Nodechat should automatically gather relevant context when the user request clearly calls for it, then disclose what it used. Mutations, privileged actions, destructive actions, public exposure, credential/security changes, and money decisions require stronger approval gates.

## Capability Map

These are fundamental capabilities, not stretch goals:

- **Agent loop:** read, reason, act, verify, iterate.
- **Filesystem:** inspect, search, edit, diff, apply, undo.
- **Commands:** diagnostics, tests, git, safe ops commands, approved risky operations.
- **Internet:** search/fetch/current-source lookup as needed.
- **Private memory:** AI History routed automatically when relevant.
- **Repo awareness:** current docs/source/git state as truth.
- **Live node awareness:** services, GPUs, Docker, vLLM/Ollama/Open WebUI, storage, network, UPS.
- **Model routing:** local Qwen/vLLM now; better local or remote models later if configured.
- **Provenance:** every important claim tied to file, command, URL, history snippet, or explicit inference.
- **Audit:** durable log of context, commands, edits, approvals, mutations.
- **Terminal UX:** fast, sessioned, commandable, recoverable.

## Risk Model

Capability is governed by risk tier, not by manual-only-everything:

| Tier | Examples | Gate |
|------|----------|------|
| **Observe** | history lookup, repo search, file read, web search/fetch, safe status commands (`git status`, `nvidia-smi`, `docker ps`, `systemctl status`) | None. Auto-route on relevance. Disclose what was used. |
| **Analyze** | summarize, compare, explain, diagnose, infer | None. Inference is internal; outputs are evidence-cited. |
| **Prepare** | draft patch, command, plan, commit message, proposed config change | None. Output is a proposal, not an action. |
| **Mutate** | apply patch, commit, push, restart service, change config, pull/fetch with side effects | Explicit approval per action. Backup/rollback metadata recorded. |
| **Dangerous** | delete files, `git push --force`, secret exposure, privileged commands, destructive hardware/network actions, BMC/IPMI changes, package install/remove, money decisions | Hard-block today. Future: multi-step approval with explicit confirmation phrase + audit. |

The control system is provenance + audit + tier-appropriate approval, not refusal of capability.

## Slash Commands Are Overrides, Not the Product

Slash commands exist for two reasons:

1. **Manual override** when the user wants to force a specific context source or skip auto-routing.
2. **Visibility** so the user can see exactly what Nodechat looked at, fetched, ran, or changed.

The default user experience should be: ask in natural language, Nodechat decides which context sources are relevant, gathers them, and answers with disclosed provenance. Slash commands are how a power user steers; they are not the only way context gets into the session.

## Auto-Routing Targets (Intended)

When the user asks something that clearly maps to a context source, Nodechat should route automatically and then disclose the routing in an evidence block:

- **Conversation** — recent turns in the current session.
- **AI History** — prior decisions, prior incidents, "what did we decide about X" style questions.
- **Repo / files** — questions that name a path, a filename, a function, a runbook, or a doc topic that exists in the repo.
- **Live node state** — questions about what is running, GPU temps, container status, free disk, current vLLM/Ollama models, current power caps.
- **Internet / current sources** — questions that name an upstream project version, a CVE, a model release, current pricing, or otherwise require fresh public data.

Auto-routing should be conservative on day one (high precision, modest recall) and grow as evidence handling matures. Even when routing is conservative, Nodechat should still disclose every source it used.

## Current Implementation State

Nodechat today is an early, partial implementation of the intended scope. What is in place:

- Local terminal chat against the OpenAI-compatible vLLM endpoint, streaming, sessioned, slash-command UX, runtime identity grounding.
- AI History KB lookup over an SSH tunnel, validated end-to-end (`/history`).
- Read-only local context tools (`/pwd`, `/tree`, `/read`, `/search-files`, `/git-status`).
- Web context tools (`/web-search`, `/web-fetch`, `/web-open`).
- Patch proposal + validate + backup + apply (`/propose-edit`, `/diff`, `/apply --check`, `/apply --confirm`).
- Read-only command capture and a narrow Git approval queue (`/cmd`, `/approvals`, `/approve`, `/reject`) covering `git fetch`, `git fetch origin`, `git fetch --all`, `git fetch --prune`, `git fetch --prune origin`, `git pull --ff-only`, and `git push`. Clean-tree preflight on `git pull --ff-only` and `git push`.
- Workspace confinement, secret-path refusal, ambiguous-hunk refusal, resolved executable provenance.
- Persistent JSONL audit log under `%USERPROFILE%\.nodehome\nodechat\audit\nodechat-audit.jsonl`; `/audit [limit]` view.
- Safety test suite in `tests/test_nodechat_safety.py` (13 tests passing as of 2026-05-15).
- Windows launchers `scripts/windows/nodechat.cmd` and `scripts/windows/nodechat-tunnel.cmd`.

What is **not** in place yet (gap between current state and intended scope):

- Auto-routing across conversation / AI History / repo / live node / internet. Today every context source is manual.
- `/undo-apply` for previously applied patches (backups exist, undo path does not).
- Live-node operator commands (vLLM/Ollama/Open WebUI/Docker/GPU/storage/UPS health) gated by tier.
- Evidence view that groups injected context by source with exact files/URLs/commands.
- Context controls: `/history-mode`, `/web-mode`, `/repo-mode`, `/evidence`, `/forget`.
- Model routing across local + remote.
- Broader command classes beyond the current Git approval set.

These are the next implementation lanes, not future-maybes.

## Near-Term Implementation Priorities

In rough order. Each lane should land with audit + tier-correct approval; capability without provenance is a regression.

1. **Auto-routing with disclosure.** Conservative-but-useful default routing for AI History, repo files, and (where safe) live node state. Always disclose: what was searched, what was read, what was fetched, what was run.
2. **Context controls.** `/history-mode auto|manual|off`, `/web-mode auto|manual|off`, `/repo-mode auto|manual|off`, `/evidence` to print the current evidence map, `/forget` to drop a context block.
3. **Undo.** `/undo-apply <id|latest>` using the existing apply-time backup metadata; new audit event on undo.
4. **Better evidence view.** Show injected context grouped by source; show exact files, URLs, commands, history snippets used; make provenance the default surface.
5. **Live node operator.** Known-safe health checks for the Nodehome stack (`nvidia-smi`, `docker ps`, `docker inspect vllm-server`, `systemctl status ollama`, `df -h`, `smartctl` reads, BMC reachability). Mutating service actions stay in the Mutate tier behind `/approve`.

## What Nodechat Is Not

For the avoidance of doubt, given previous scope drift:

- Not a "cautious chat utility."
- Not "explicit-only" by philosophy. Manual-only is a transient implementation state, not the product.
- Not a no-internet, no-files tool.
- Not "maybe later it can become an operator." It is intended to be an operator now; capability is being built deliberately.
- Not a Codex/Claude Code clone either. It targets the same capability class but is tailored to this local stack: vLLM/Ollama on 3x 3090, AI History on the homelab node, the Nodehome repo as the source of truth.

## Related Docs

- [`nodechat-terminal.md`](nodechat-terminal.md) — operational usage, slash command reference, sessions, env vars, Windows launcher path.
- [`ai-history-knowledge-base.md`](ai-history-knowledge-base.md) — the private memory backend Nodechat reads from.
- [`upgrade-cadence.md`](upgrade-cadence.md) — version-pinning policy that applies when Nodechat surfaces upstream version signals.
- [`hardware-upgrade-roadmap.md`](hardware-upgrade-roadmap.md) — node hardware roadmap referenced by live-node operator features.
