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
- **Model routing:** local profiles by default, auto-routed local dispatch, and explicit env-gated remote profiles when configured.
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
- **Model profiles.** Built-in profiles map capability names to validated local lanes: `fast` -> `mistral-small3.1:24b` on Ollama, `strong` -> `Qwen/Qwen2.5-32B-Instruct-AWQ` on vLLM, and `deep` -> `llama3.3:70b-instruct-q4_K_M` on Ollama. `/profile` lists/switches profiles; `/model <profile>` resolves profile names before falling back to literal model IDs. The active profile/model/endpoint are disclosed before each assistant reply and recorded in `model_dispatched` audit events. User-defined profiles are restricted to local/private endpoints.
- **Remote profiles (Phase 3).** OpenAI and Anthropic profiles are built in but env-gated: they appear only when the matching API key and model env vars exist. They are also session-gated: `/remote-models enable` is required before `/profile openai`, `/profile anthropic`, `/model <remote>`, or `/model-mode <remote>` can dispatch off-box. Remote profiles are explicit-only; `auto` model routing never chooses them. `/costs` reports per-session remote cost estimates from prompt/response character counts and optional per-million-token env vars. `model_dispatched` audit rows record `remote`, `provider_kind`, estimated input/output tokens, and estimated cost.
- **Model auto-routing (Phase 2).** `/model-mode auto|manual|<profile>` controls per-turn dispatch (default `auto`). `auto` defaults to `fast` and lifts to `strong` on long prompts (>800 chars), code markers (triple backticks, `def`/`class`/`function`/`import`/`return`/`async`/`await`/`traceback`/`exception`/`error:`), analysis verbs (`analyze`/`review`/`compare`/`diagnose`/`refactor`/`design`/`deep dive`/`walk me through`), history-routing intent, or multi-file repo routing. `deep` and remote profiles are never auto-selected; user must pin them explicitly. Before routing to `strong`, vLLM availability is checked via cached `/models` probe (60s TTL); if vLLM is unreachable the dispatch falls back to `fast` and discloses the reason. **Per-turn dispatch only -- session.profile / .model / .base_url stay unchanged unless the user runs `/profile` or `/model`.** Disclosure shows rationale on auto-routed turns: `[model: strong <- auto-routed: long prompt; code markers]` or `[model: fast <- strong unavailable: vLLM probe failed (3012ms)]`. New audit event `auto_route_model` fires on lift-to-strong success and on fallback; `model_dispatched` continues per-turn with the dispatched profile.
- AI History KB lookup over an SSH tunnel, validated end-to-end (`/history`).
- Read-only local context tools (`/pwd`, `/tree`, `/read`, `/search-files`, `/git-status`).
- Web context tools (`/web-search`, `/web-fetch`, `/web-open`) plus conservative auto-routing for fresh public data.
- Patch proposal + validate + backup + apply + undo (`/propose-edit`, `/diff`, `/apply --check`, `/apply --confirm`, `/undo-apply [n|latest] [--check]`).
- Read-only command capture and a narrow Git approval queue (`/cmd`, `/approvals`, `/approve`, `/reject`) covering `git fetch`, `git fetch origin`, `git fetch --all`, `git fetch --prune`, `git fetch --prune origin`, `git pull --ff-only`, and `git push`. Clean-tree preflight on `git pull --ff-only` and `git push`.
- **Auto-routing for AI History and repo files**, conservative day-one heuristics (Observe tier). History routes on prior-decision phrasing (`what did we …`, `remind me`, `previously`, `history of …`, `prior decision/incident/run`, etc.); repo routes on concrete artifacts only (named files like `CURRENT_STATE`/`SESSION_LOG`/`CLAUDE.md`/`SCRATCH.md`/`ATTITUDE.md`, known runbook stems, and path-like tokens such as `docs/...`/`scripts/...`/`sweeps/...`/`tests/...`). Vague topic phrases and bare filenames do not auto-route; users invoke `/read` for those. Repo auto-routing reads at most two files per turn, applies the same workspace confinement and secret-path refusals as `/read`, and never blocks the chat turn on routing failure.
- **Web auto-routing**, conservative day-one heuristics (Observe tier). Direct `http://`/`https://` URLs auto-fetch. Prompts with explicit web/search language or fresh-public-data signals (`latest`, `current`, release, version, CVE, vulnerability, pricing, availability, market, etc.) plus a public object route through DuckDuckGo HTML search. Local-only status phrasing such as "current vLLM status on our node" intentionally does not web-route. Auto web uses a short timeout, never blocks the chat turn beyond its bounded fetch/search call, and records errors as disclosed routing skips.
- **Live-node operator checks**, conservative day-one Observe tier. `/live [all|health|gpu|power|docker|vllm|ollama|storage|bmc|ups|smart /dev/<device>]` runs fixed status commands locally or through optional SSH (`NODECHAT_LIVE_SSH` / `--live-ssh`, default root `~/nodehome`). Auto live routing triggers only on clear live-status prompts about the node, GPUs, vLLM/Ollama/Open WebUI/Docker, storage, BMC/IPMI, UPS, or power caps. It injects `LIVE_NODE_STATUS` with commands, exit codes, executable provenance, and bounded output. Selected service restarts are Mutate-tier approval rows through `/approve`.
- Live routing uses `/live-mode auto|manual|off`, discloses as `live(...)` in the auto-routing line, and records `auto_route_live` plus `live_check_executed` audit events.
- **Disclosure line printed before every assistant reply** that auto-routed anything, e.g. `[auto-routed: history(2403 chars, "what did we decide about gpu2") | repo(read docs/CURRENT_STATE.md) | web(search 8 results, "latest vLLM release")]`. Skips and errors are disclosed inline (`history(error: …)`, `web(search error: …)`).
- **Context controls.** `/history-mode auto|manual|off`, `/repo-mode auto|manual|off`, `/web-mode auto|manual|off`, `/live-mode auto|manual|off` (defaults `auto`); `/evidence` groups active blocks by source with counts, total chars, reference summaries, and global indexes; `/forget [n|latest|all]` drops blocks.
- **Structured provenance on every context block.** Each block carries `source` (e.g. `auto-history`, `auto-repo`, `manual-read`, `manual-cmd`, `manual-approve`, …) and a `provenance` dict (paths, queries, exit codes, approval ids, etc.). Legacy blocks render under `manual-legacy`.
- **Audit covers routing too.** `auto_route_history`, `auto_route_repo`, and `auto_route_web` events log status (`ok|error`), query/path/URL/action, chars/results, and reason on skip.
- Workspace confinement, secret-path refusal, ambiguous-hunk refusal, resolved executable provenance.
- Persistent JSONL audit log under `%USERPROFILE%\.nodehome\nodechat\audit\nodechat-audit.jsonl`; `/audit [limit]` view.
- Safety test suite in `tests/test_nodechat_safety.py` (80 tests passing).
- **Auto-routing recall pass — Phase A (measurement infrastructure) shipped.** Labeled corpus of 100 realistic prompts in `tests/routing_corpus.py` covering history positives (incl. Phase B widening targets), repo positives (named files / runbook stems / path tokens / multi-file), web positives (URL fetch + fresh-public search), live positives (one per check), neutral/general prompts, and adversarial guardrails. Harness emits per-router precision/recall + FP/FN lists and runs as both a CLI (`py -3 tests/routing_corpus.py`) and a regression test class.
- **Auto-routing recall pass — Phase B history landed.** History patterns split into TIGHT (already project-bound by phrasing) and BROAD ("remind me", "previously", "history of", "have we ever", "has X ever", "what was our reasoning") with the BROAD set requiring co-occurrence with `HISTORY_PROJECT_CONTEXT_RE` (we / our / nodehome / gpu / vllm / cable / rack / etc.). Three new broad patterns added for the FN cases. History router went from precision 0.81 / recall 0.81 to **1.00 / 1.00**; three history guardrails (general-knowledge "history of the mongol empire" / "previously the romans..." / personal-reminder "remind me to call mom") now refuse correctly and were removed from `PHASE_B_GUARDRAIL_TARGETS`.
- **Auto-routing recall pass — Phase B web landed.** `WEB_LOCAL_ONLY_RE` widened with project-ownership constructions (`we (built|made|trained|configured|installed|capped|ordered|...)`, "across all three", "all three cards", "the (node|box|rack|chassis|...)", "on the (node|box|...)", "in (the|a) (rack|container|...)", "container", "containers", "power draw", "power cap", "fan curve", etc.) so local-status prompts no longer trip the search heuristic. New fourth `detect_web_targets` branch: explicit "search/look up/online/etc." + freshness signal + no local context routes search even without a hit on `WEB_PUBLIC_OBJECT_RE` -- this catches proprietary part numbers like SF-1600F14HT that aren't in the public-object list. Web router went from precision 0.82 / recall 0.93 to **1.00 / 1.00**; one web guardrail (g008 "the latest model we trained") removed from `PHASE_B_GUARDRAIL_TARGETS`.
- **Auto-routing recall pass — Phase B live landed.** Three changes: (1) `LIVE_OBJECT_RE` extended with `box` so "what's running on the box" routes through the docker fallback; (2) new cross-router guardrails `LIVE_PUBLIC_DEST_RE` (github / huggingface / amazon / ebay / online / etc.) and `LIVE_LOCAL_HINT_RE` (our / my / nodehome / homelab / "the node" / "in a container" / etc.) -- live now refuses if the prompt has a public-destination signal or a `WEB_EXPLICIT_RE` signal AND no local hint, so prompts like "current ollama version on github" or "look up vllm benchmarks online" no longer trip live; (3) the over-broad health fallback split into "explicit health words always add health" + "project-context tokens (stack/nodehome/homelab/the node) only add health when no specific check has fired", so "current gpu temperature on the node" returns just `['gpu']` instead of `['health', 'gpu']`. Live router went from precision 0.78 / recall 0.68 to **1.00 / 1.00**; two live guardrails (g006 "current vLLM status on our node", g007 "what's running on the box") removed from `PHASE_B_GUARDRAIL_TARGETS`. **Phase B complete on every router; the guardrail set is empty.**
- Phase A + Phase B baseline: repo 1.00/1.00; history 1.00/1.00; web 1.00/1.00; live 1.00/1.00. Phase B target (precision >= 0.95, recall >= 0.95, zero guardrail failures) met across all four routers.
- **Broader operator approvals — first iteration shipped.** `/live` now exposes a small allowlisted Mutate-tier surface alongside the existing Observe-tier reads. Diagnostics (`/live ps`, `/live logs <vllm|open-webui|ollama>`, `/live journal ollama`, `/live inspect <vllm|open-webui>`) run immediately. Mutations (`/live restart vllm-server`, `/live restart open-webui`) queue an approval row of class `live-mutation` and only execute after `/approve <id>`. Hard guardrails: no arbitrary container names, no arbitrary journalctl units, no `--follow`, no shell composition, no restart without `/approve`. `/live restart ollama` is explicitly deferred until a NOPASSWD sudoers entry is installed (documented in `live-mutations.md`). New audit events: `live_diag_executed`, `live_mutation_queued`, `live_mutation_executed`, `live_mutation_blocked`, `live_mutation_refused`. Full reference: [`live-mutations.md`](live-mutations.md).
- Windows launchers `scripts/windows/nodechat.cmd` and `scripts/windows/nodechat-tunnel.cmd`.

What is **not** in place yet (gap between current state and intended scope):

- Additional Mutate-tier ops beyond `docker restart` for `vllm-server` and `open-webui`. Specifically: `systemctl restart ollama` (gated on the sudoers entry), `docker compose up/down`, config edits to `/etc/systemd/system/*.service.d/override.conf`, BMC password rotation, etc. Each new op needs a fixed argv, a runbook entry, and a regression test.

These are the next implementation lanes, not future-maybes.

## Near-Term Implementation Priorities

In rough order. Each lane should land with audit + tier-correct approval; capability without provenance is a regression.

1. **Auto-routing recall pass — corpus growth.** Phase B is complete (all routers 1.00 / 1.00 on the 100-prompt corpus). The next iteration is corpus growth: add prompts surfaced by real Nodechat use that don't currently route the way the user expects. This is now a maintenance loop, not a discrete lane.
2. **Broader operator approvals — additional ops.** First iteration covers `docker restart` for two services. Next-up additions: `systemctl restart ollama` once the sudoers entry is installed, then narrow `docker compose up -d <service>` for restart-equivalent flows. Each new op follows the same pattern: fixed argv in `LIVE_MUTATION_OPS`, runbook entry, regression test that asserts queue + execute + audit.
3. **Model routing refinement.** Remote profiles are in place. Next refinements are provider usage-accounting when available, live smoke validation with real keys only when intentionally enabled, and explicit local/remote routing policy improvements after real use.

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
