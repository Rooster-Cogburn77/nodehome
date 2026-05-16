# Nodechat Terminal Client

Status: early implementation of the Nodehome local agentic terminal environment. Authoritative scope and product philosophy live in [`nodechat-scope.md`](nodechat-scope.md); this doc covers operational usage, slash commands, env vars, and current safety posture.

`scripts/nodechat.py` is the repo-owned terminal client for the local model stack. It runs against local OpenAI-compatible endpoints and explicit env-gated remote profiles, keeps sessions, exposes model profiles plus slash-command tooling for context/edits/commands, and writes a persistent audit log of significant tool actions.

Auto-routing is on for AI History, repo files, and fresh public web context. When the prompt clearly calls for prior decisions (`what did we …`, `remind me`, `previously`, `history of …`, `prior decision/incident`, etc.) Nodechat auto-injects an AI History block. When the prompt names a concrete repo artifact (`CURRENT_STATE`, `SESSION_LOG`, `CLAUDE.md`, `SCRATCH.md`, `ATTITUDE.md`, a known runbook stem like `nodechat-scope`, or a path token like `docs/...`/`scripts/...`) Nodechat auto-reads the file with the same caps and safety checks as `/read`. When the prompt includes a URL, Nodechat auto-fetches it; when the prompt clearly needs fresh public data (`latest`, releases, versions, CVEs, current pricing/availability, etc.) and names a public object, Nodechat auto-routes a bounded DuckDuckGo HTML search. Vague local-status phrases, vague repo topic phrases, and bare filenames do not auto-route. Every assistant turn prints a one-line model disclosure; routed turns include the routed sources in that same disclosure. Slash commands remain the manual override and the visibility surface.

Live-node auto-routing is also in place for fixed Observe-tier checks. Clear live Nodehome status prompts can inject `LIVE_NODE_STATUS` for GPUs, vLLM/Ollama/Open WebUI/Docker, storage, BMC/IPMI, UPS, or power caps. Use `/live-mode auto|manual|off` to control that lane.

Mutations are tier-gated. Patch application is approval-confirmed with an on-disk backup. Selected Git network/update commands queue for explicit `/approve`. Destructive, privileged, package-manager, and arbitrary-network commands are refused today and will move into a multi-step approval tier as the safety model matures. All local file/command paths are confined to the configured Nodechat workspace (`C:\Users\bmoor\Local_AI` under the Windows launcher).

A small `NODECHAT_RUNTIME` system message is injected on every request so the model answers identity questions from the actual configured profile, model, and endpoint instead of inventing one.

## Model Profiles

Nodechat has built-in model profiles for the validated local lanes:

```text
fast    mistral-small3.1:24b              Ollama   ~51 tok/s
strong  Qwen/Qwen2.5-32B-Instruct-AWQ     vLLM     ~59 tok/s
deep    llama3.3:70b-instruct-q4_K_M      Ollama   ~8-15 tok/s
```

`strong` is the default profile when the configured model/endpoint match the validated vLLM backend:

```text
model: Qwen/Qwen2.5-32B-Instruct-AWQ
endpoint on homelab: http://127.0.0.1:8000/v1
endpoint from LAN/Windows: http://192.168.1.198:8000/v1
```

Use `/profile` to list profiles and `/profile <name>` or `/model <name>` to switch. `/model <literal-model-id>` still works for backward compatibility; profile names resolve first. `/model-mode auto|manual|<profile>` controls per-turn dispatch: `auto` only selects local `fast` or `strong`, and any pinned profile name dispatches that profile each turn. Optional user profiles can be added at:

```text
~/.nodehome/nodechat/profiles.json
```

The built-in `strong` profile follows the active `NODECHAT_BASE_URL` / `--base-url`, so the Windows launcher keeps using the LAN vLLM endpoint. Set `NODECHAT_OLLAMA_BASE_URL` if the `fast` and `deep` Ollama profiles should use a LAN endpoint instead of `http://localhost:11434/v1`.

User-defined profiles remain local/private endpoints only (`localhost`, loopback, LAN/private IPs, or `host.docker.internal`) so a `profiles.json` edit cannot silently send data off-box.

Remote profiles are built in but env-gated and session-gated. They do not appear unless the matching key and model env vars are present. They do not dispatch unless the user enables them for the current session:

```text
/remote-models status
/remote-models enable
/remote-models disable
/profile openai
/profile anthropic
/model-mode openai
/costs
```

Remote profiles are explicit-only. `auto` model routing never selects `openai` or `anthropic`; the user must run `/profile <remote>`, `/model <remote>`, or `/model-mode <remote>` after `/remote-models enable`.

Remote env vars:

```text
NODECHAT_OPENAI_API_KEY or OPENAI_API_KEY
NODECHAT_OPENAI_MODEL
NODECHAT_OPENAI_BASE_URL                 optional, default https://api.openai.com/v1
NODECHAT_OPENAI_INPUT_PER_MTOK           optional, for cost estimate
NODECHAT_OPENAI_OUTPUT_PER_MTOK          optional, for cost estimate

NODECHAT_ANTHROPIC_API_KEY or ANTHROPIC_API_KEY
NODECHAT_ANTHROPIC_MODEL
NODECHAT_ANTHROPIC_BASE_URL              optional, default https://api.anthropic.com/v1
NODECHAT_ANTHROPIC_INPUT_PER_MTOK        optional, for cost estimate
NODECHAT_ANTHROPIC_OUTPUT_PER_MTOK       optional, for cost estimate
```

Remote cost tracking is a session estimate. Until provider usage accounting is wired in, Nodechat estimates tokens as `chars / 4`, multiplies by the optional per-million-token env vars above, records the estimate in `model_dispatched`, and rolls it up in `/costs`.

Run on the homelab node:

```bash
python3 ~/nodehome/scripts/nodechat.py
```

Run from Windows against the homelab:

```powershell
python scripts\nodechat.py --base-url http://192.168.1.198:8000/v1
```

Preferred Windows launcher:

```bat
C:\Users\bmoor\Local_AI\scripts\windows\nodechat.cmd
```

One-shot prompt from Windows:

```powershell
python scripts\nodechat.py --base-url http://192.168.1.198:8000/v1 --once "Say hello in one sentence."
```

## Sessions

Sessions are saved outside the repo:

```text
~/.nodehome/nodechat/sessions/
```

Useful commands:

```text
/sessions
/resume <session-id-prefix>
/new
/save
/exit
```

## Slash Commands

Inside `nodechat`:

```text
/help
/profile [name]
/model [name]
/model-mode [auto|manual|fast|strong|deep|profile]
/remote-models [status|enable|disable]
/costs
/endpoint [url]
/system [text]
/history <query>
/history-mode [auto|manual|off]
/repo-mode [auto|manual|off]
/web-mode [auto|manual|off]
/live-mode [auto|manual|off]
/evidence
/forget [n|latest|all]
/pwd
/tree [path]
/read <path>
/search-files <query> [path]
/git-status
/web-search <query>
/web-fetch <url>
/web-open <url>
/live [all|health|gpu|power|docker|vllm|ollama|storage|bmc|ups|smart /dev/<device>]
/live ps
/live logs <vllm|open-webui|ollama>
/live journal ollama
/live inspect <vllm|open-webui>
/live restart <vllm-server|open-webui>      (queues for /approve)
/propose-edit <path> :: <instruction>
/diff [all]
/apply [n|latest] [--check|--confirm]
/undo-apply [n|latest] [--check]
/cmd <command>
/context
/clear-context
/status
/paste
```

`/paste` starts a multi-line prompt. End it with a single `.` on its own line.

## AI History Integration

AI History is auto-routed on prior-decision phrasing (`what did we …`, `remind me`, `previously`, `history of …`, `prior decision/incident/run`, etc.). Routing prints a disclosure line and writes an `auto_route_history` audit event. Use `/history <query>` to force a lookup with an arbitrary phrasing, `/history-mode manual` to require explicit invocation, or `/history-mode off` to disable history routing entirely. Failures (endpoint unreachable, token missing) are disclosed in the routing line and never block the chat turn.

```text
/history what did we decide about GPU2 and the pigtail rule
```

That calls the AI History KB `/prompt` endpoint and injects the returned `HISTORY_CONTEXT` as a system context block for future turns in the current session.

On the homelab node, the default history endpoint is:

```text
http://127.0.0.1:8765
```

If running from Windows, keep the history service private and use an SSH tunnel. In a first Command Prompt:

```bat
C:\Users\bmoor\Local_AI\scripts\windows\nodechat-tunnel.cmd
```

Leave that SSH window open. In a second Command Prompt:

```bat
set NODECHAT_HISTORY_TOKEN=<saved-ai-history-token>
C:\Users\bmoor\Local_AI\scripts\windows\nodechat.cmd
```

This is the preferred Windows path because it does not expose the AI History API to the LAN. The tunnel target is `172.17.0.1:8765` because the service is bound to Docker's bridge address for Open WebUI access.

To avoid setting the token every time, create this local file outside the repo:

```bat
mkdir %USERPROFILE%\.nodehome
notepad %USERPROFILE%\.nodehome\nodechat.env
```

Contents:

```text
NODECHAT_HISTORY_TOKEN=paste-saved-token-here
```

`AI_HISTORY_TOKEN=paste-saved-token-here` also works; the Windows launcher maps it to `NODECHAT_HISTORY_TOKEN` before starting Nodechat.

Do not put this token in the repo.

Validated 2026-05-15 from Windows:

```text
/status -> AI History endpoint: OK (http://127.0.0.1:8765, total=279699)
/history what did we decide about GPU2 and the pigtail rule -> history context added
follow-up summary -> model answered from injected pigtail-rule context
```

Environment variables:

```text
NODECHAT_BASE_URL
NODECHAT_MODEL
NODECHAT_API_KEY
NODECHAT_HISTORY_URL
NODECHAT_HISTORY_TOKEN
NODECHAT_LIVE_SSH
NODECHAT_LIVE_ROOT
NODECHAT_SESSION_ROOT
NODECHAT_WORKSPACE
NODECHAT_TEMPERATURE
NODECHAT_MAX_TOKENS
NODECHAT_OPENAI_API_KEY
OPENAI_API_KEY
NODECHAT_OPENAI_MODEL
NODECHAT_OPENAI_BASE_URL
NODECHAT_OPENAI_INPUT_PER_MTOK
NODECHAT_OPENAI_OUTPUT_PER_MTOK
NODECHAT_ANTHROPIC_API_KEY
ANTHROPIC_API_KEY
NODECHAT_ANTHROPIC_MODEL
NODECHAT_ANTHROPIC_BASE_URL
NODECHAT_ANTHROPIC_INPUT_PER_MTOK
NODECHAT_ANTHROPIC_OUTPUT_PER_MTOK
```

Windows launcher scripts:

```text
scripts/windows/nodechat.cmd
scripts/windows/nodechat-tunnel.cmd
```

`scripts/windows/nodechat.cmd` sets the default Nodechat workspace to the repo root (`C:\Users\bmoor\Local_AI`) so `/read`, `/tree`, `/search-files`, and `/git-status` work from the correct project even when the Command Prompt starts in `C:\Users\bmoor`.

## Local Context Tools

Repo file context auto-routes on concrete artifacts. When the prompt names `CURRENT_STATE`, `SESSION_LOG`, `CLAUDE.md`, `SCRATCH.md`, `ATTITUDE.md`, a known runbook stem (`nodechat-scope`, `ipmi-recovery`, `home-media-server`, …), or a path token (`docs/...`, `scripts/...`, `sweeps/...`, `tests/...`, `memory/...`), Nodechat reads the file with the same caps and safety checks as `/read` and adds a disclosed context block. At most two files auto-route per turn. Vague topic phrases ("current state of the build", "this codebase") and bare filenames do not route. Use `/repo-mode off` to disable repo routing.

Manual context tools (also stay available as the visibility surface):

```text
/pwd
/tree docs
/read docs\CURRENT_STATE.md
/search-files gpu2 docs
/git-status
/evidence
/forget latest
```

Rules:

- `/read` is text-only and size-capped; auto-repo routing uses the same path.
- `/tree` is depth/result capped.
- `/search-files` searches text files only and returns bounded filename/line matches.
- `/git-status` runs only the fixed read-only `git status --short --branch` command.
- Secret-ish paths and generated/private stores are refused rather than injected, both for manual `/read` and for auto-repo routing.
- `/evidence` groups active context blocks by source, shows per-source counts, char totals, reference summaries, and the global indexes used by `/forget`. `/forget [n|latest|all]` drops one or all of them.

## Web Context Tools

Web fetch and search are auto-routed for direct URLs and prompts that clearly need fresh public data, and can also be invoked explicitly. Auto-routed web uses the same bounded fetch/search code as manual commands, a shorter timeout, disclosure, provenance, and `auto_route_web` audit events. Fetched text stays transient unless the user saves it.

```text
/web-search qwen2.5 awq vllm
/web-fetch https://example.com
/web-open https://example.com
```

`/web-search` uses DuckDuckGo HTML results and stores titles/URLs as leads. Use `/web-fetch` or `/web-open` on a result before treating the source text as evidence.

Use `/web-mode manual` to require explicit `/web-search` or `/web-fetch`. Use `/web-mode off` to disable web routing for the session. Manual web commands still work when mode is `manual`; `off` only affects auto-routing.

## Live Node Tools

Live-node context auto-routes for clear Nodehome status prompts and can also be invoked explicitly:

```text
/live
/live gpu vllm
/live all
/live smart /dev/sda
/live-mode auto
/live-mode manual
/live-mode off
```

Default `/live` runs the fixed `health` check. `/live all` currently expands to health, GPU, power, Docker, vLLM, Ollama, and storage checks.

Beyond the fixed checks, `/live` also exposes a small allowlisted surface of read-only diagnostics and approval-gated mutations (full reference: [`live-mutations.md`](live-mutations.md)):

```text
# Observe tier -- run immediately
/live ps                      # docker ps -a
/live logs vllm               # docker logs --tail 200 vllm-server
/live logs open-webui         # docker logs --tail 200 open-webui
/live logs ollama             # alias of /live journal ollama
/live journal ollama          # journalctl -u ollama --no-pager -n 200
/live inspect vllm            # docker inspect vllm-server
/live inspect open-webui      # docker inspect open-webui

# Mutate tier -- queue for /approve
/live restart vllm-server     # docker restart vllm-server  (queued)
/live restart open-webui      # docker restart open-webui   (queued)
/live restart ollama          # sudo -n /bin/systemctl restart ollama  (queued)
```

`/live restart …` does not execute. It queues an approval row (class `live-mutation`) and prints an `APPROVAL_REQUIRED` block. The restart only runs after `/approve <id>`. Audit trail records the queued argv, the executed argv, exit code, executable provenance, and target (`local` or `ssh:user@host`) on separate `live_mutation_queued` and `live_mutation_executed` events.

Hard guardrails: no arbitrary container names, no arbitrary journalctl units, no templated systemd units, no `--follow`, no shell composition, no restart without `/approve`.

By default, live checks run from the current machine. From Windows, point Nodechat at the homelab with:

```bat
set NODECHAT_LIVE_SSH=bmoore_77@192.168.1.198
set NODECHAT_LIVE_ROOT=~/nodehome
```

Automatic live checks use `ssh -o BatchMode=yes`, so they require key-based SSH or another noninteractive auth path. If SSH is not configured, the check records an error block and the chat turn continues.

Live context is injected as `LIVE_NODE_STATUS` with the check name, target, command, exit code, resolved executable when available, and bounded command output. The audit log records `live_check_executed` for manual `/live` and `auto_route_live` for automatic live routing.

## Proposed Edit Tools

Nodechat can ask the local model for a diff proposal, but it does not write or apply the result:

```text
/propose-edit docs\runbooks\nodechat-terminal.md :: add a warning that web search snippets are not proof
/diff
/diff all
```

Rules:

- The syntax requires `::` between the path and the instruction.
- The command reads one bounded text file and asks the model for a unified diff.
- The proposal is stored in the current session only.
- `/diff` prints the latest proposal; `/diff all` prints every proposal stored in that session.
- Applying a proposal is available through `/apply --confirm`; no freeform write command exists.
- `/apply --check` validates the latest proposal without writing.
- `/apply --confirm` applies the latest proposal after validation and writes a backup under `~/.nodehome/nodechat/backups/`.
- `/apply <n> --confirm` applies a specific proposal by its session index.
- `/undo-apply [n|latest]` restores an applied proposal from its apply-time backup.
- `/undo-apply --check` validates that the file still matches the applied proposal without writing.
- Undo refuses if the target file changed after apply, preventing clobber of newer work.

## Command Tools

Phase 5A implements read-only command output capture plus a narrow approval queue for selected Git network/update commands:

```text
/cmd git status --short --branch
/cmd git diff --stat
/cmd rg Nodechat docs
/cmd dir scripts
/cmd type docs\runbooks\nodechat-terminal.md
/cmd git fetch
/cmd git pull --ff-only
/cmd git push
/approvals
/approve a1
/reject a1
/audit 20
```

Output is injected as:

```text
COMMAND_OUTPUT
timestamp: 2026-05-15T12:00:00+00:00
cwd: C:\Users\bmoor\Local_AI
class: read-only
command: git status --short --branch
exit_code: 0
truncated: false
executable: C:\Program Files\Git\cmd\git.exe

## main...origin/main
```

Rules:

- Only allowlisted read-only commands run immediately.
- Selected Git network/update commands queue for `/approve`: `git fetch`, `git fetch origin`, `git fetch --all`, `git fetch --prune`, `git fetch --prune origin`, `git pull --ff-only`, and `git push`.
- `/approve <id>` reclassifies the queued command before execution and records the resulting command output with `approval_id: ...`.
- `git pull --ff-only` and `git push` require a clean working tree before execution. If the tree is dirty, the approval is marked `blocked` and the Git command is not run.
- Refused commands are still logged as `COMMAND_OUTPUT` with `exit_code: refused`.
- Allowed examples: read-only `git` subcommands, `rg` without risky traversal/preprocessor flags, `dir`, `ls`, `type`, `cat`, `pwd`, and version checks.
- Refused examples: `git add`, `git commit`, package-manager commands, arbitrary network commands, destructive deletes, privileged service commands, and unknown commands.
- `rg --pre`, `rg --hidden`, `rg --no-ignore`, and `git --output` / `git --ext-diff` style paths are refused in this phase.
- This is not arbitrary shell. Commands are parsed and run without shell metacharacter expansion.
- External executables are resolved through `PATH` and recorded in the output block as `executable: ...`.
- Path arguments outside the Nodechat workspace are refused.

Persistent audit:

- Audit file: `%USERPROFILE%\.nodehome\nodechat\audit\nodechat-audit.jsonl` by default.
- `/audit [limit]` prints recent audit events.
- Logged events include queued approvals, rejected approvals, approved command execution/blocking, refused commands, read-only command execution, `/apply --check`, `/apply --confirm`, `/undo-apply --check`, and `/undo-apply`.
- Audit rows store command/proposal metadata, session id, workspace, status, executable, backup path where relevant, and output digest/size. They intentionally do not duplicate full command output.

## Safety Tests

The Nodechat safety boundary has focused stdlib unit tests:

```powershell
py -3 -m unittest tests\test_nodechat_safety.py
```

Current coverage:

- Workspace confinement blocks outside paths.
- `/read` refuses outside-workspace files.
- `/cmd` classifier refuses outside paths, risky `rg` flags, and network commands.
- `/cmd` queues selected Git network/update commands instead of executing them.
- `/approve` executes a queued command once and records `approval_id`.
- `/approve` blocks dirty-tree `git pull --ff-only` / `git push` before execution.
- Non-approved Git variants such as `git push --force`, `git push origin main`, and `git fetch origin main` do not queue.
- `/apply` refuses ambiguous repeated hunks.
- `/apply` still works when repeated hunk context has an exact preferred location.
- `/cmd` read-only subprocess execution records a resolved executable path.
- Persistent audit records refused commands, queued approvals, executed approvals, blocked approvals, and apply check/confirm events.
- `/evidence` groups blocks by source while preserving global `/forget` indexes.
- Live routing detection avoids history-style prompts such as "what did we decide about GPU2?"
- Live checks can run through an optional SSH target, validate SMART device paths, disclose provenance, and respect `/live-mode off`.
- Remote profiles are env-gated, require `/remote-models enable`, never auto-select in model `auto` mode, support explicit OpenAI/Anthropic dispatch shims, and record remote cost estimates.

## Capability Lanes

Capability is governed by risk tier, not by explicit-only-everything. See [`nodechat-scope.md`](nodechat-scope.md) for the tier definitions (Observe / Analyze / Prepare / Mutate / Dangerous) and the auto-routing roadmap. This section tracks what is implemented per capability lane.

### Observe lane (Done)

```text
chat with local vLLM (streaming, sessioned, slash-command UX)
/history <query>           AI History KB injection (also auto-routed on prior-decision phrasing)
/read <path>               text-only, size-capped (also auto-routed on concrete repo artifacts)
/tree [path]               depth/result capped
/search-files <q> [path]   text files only
/git-status                fixed `git status --short --branch`
/pwd
/web-search <query>        DuckDuckGo HTML, leads only
/web-fetch <url>           bounded text fetch
/web-open <url>            same as fetch but opens in session view
/live [check]              fixed live-node status checks; optional SSH target
/cmd <read-only command>   allowlisted: git read subcommands, rg, dir/ls, type/cat, pwd, --version
/profile [name]            local profiles and env-gated remote profiles
/model-mode [auto|manual|profile]
/remote-models [status|enable|disable]
/costs
/history-mode [auto|manual|off]
/repo-mode [auto|manual|off]
/web-mode [auto|manual|off]
/live-mode [auto|manual|off]
/evidence                  group context blocks by source with provenance
/forget [n|latest|all]     drop a context block
```

Auto-routing covers AI History (prior-decision phrasing), repo files (concrete artifacts only), fresh public web context (direct URLs and current/release/CVE/pricing-style prompts), and live-node status checks with disclosed provenance and audit. `/cmd` remains manual-only today.

### Prepare lane (Done)

```text
/propose-edit <path> :: <instruction>   single-file unified-diff proposal, stored in session
/diff [all]                             print latest or all stored proposals
/apply --check                          validate stored proposal against current file, no write
/undo-apply --check                     validate undo against current file, no write
```

`/propose-edit` strips outer Markdown code fences before storing. `/apply --check` refuses ambiguous repeated hunks rather than fuzzy-applying the first match.

### Mutate lane (Partial)

```text
/apply [n|latest] --confirm    write backup, then apply stored proposal
/undo-apply [n|latest]        restore apply-time backup after safety check
/cmd git fetch                 queues for /approve
/cmd git fetch origin          queues
/cmd git fetch --all           queues
/cmd git fetch --prune         queues
/cmd git fetch --prune origin  queues
/cmd git pull --ff-only        queues; clean-tree preflight on /approve
/cmd git push                  queues; clean-tree preflight on /approve
/approvals                     list pending/queued approvals
/approve <id|latest>           run the queued command once, record approval_id
/reject <id|latest>            mark the queued command rejected
```

Backups land under the Nodechat session backup directory outside the repo. Resolved executable provenance is recorded on every subprocess-backed command. Non-allowlisted Git variants (`git push --force`, `git push origin main`, `git fetch origin main`, etc.) do not queue.

Gaps in this lane: broader command classes beyond the current Git approval set, and live-node operator mutations (`docker restart`, `systemctl restart`) gated by tier.

### Dangerous lane (Hard-blocked today)

Refused with a structured `COMMAND_OUTPUT` row, never queued:

```text
package-manager commands (apt, pip, npm, ...)
privileged commands (sudo, su, ...)
destructive commands (rm, del, mv over existing, ...)
arbitrary network commands (curl, wget outside web tools, ssh, scp, ...)
write Git commands (git add, git commit, git reset --hard, git push --force, ...)
unknown commands
path arguments outside the Nodechat workspace
hidden-traversal flags (rg --hidden, rg --no-ignore, ...)
```

The future direction for this lane is multi-step approval (explicit confirmation phrase + audit) for individually justified actions, not unconditional refusal. Hard-block stays the default until that approval model exists.

## Safety Model

Risk tier governs what runs without prompting, what queues for approval, and what is hard-blocked today; the [scope doc](nodechat-scope.md#risk-model) is authoritative. Provenance + audit + tier-correct approval is the control system. Capability with evidence is the goal; refusal is the fallback when the safety model has not yet caught up.
