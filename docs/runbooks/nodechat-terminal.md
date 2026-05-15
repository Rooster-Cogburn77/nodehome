# Nodechat Terminal Client

Status: early implementation of the Nodehome local agentic terminal environment. Authoritative scope and product philosophy live in [`nodechat-scope.md`](nodechat-scope.md); this doc covers operational usage, slash commands, env vars, and current safety posture.

`scripts/nodechat.py` is the repo-owned terminal client for the local model stack. It runs against any OpenAI-compatible endpoint (today: vLLM on the homelab node), keeps sessions, exposes slash-command tooling for context/edits/commands, and writes a persistent audit log of significant tool actions.

Today, every context source (AI History, repo files, web, commands) is gathered through an explicit slash command. Auto-routing across those sources with disclosed provenance is on the near-term roadmap; see [`nodechat-scope.md`](nodechat-scope.md). Slash commands stay as manual overrides and as the visibility surface even after auto-routing lands.

Mutations are tier-gated. Patch application is approval-confirmed with an on-disk backup. Selected Git network/update commands queue for explicit `/approve`. Destructive, privileged, package-manager, and arbitrary-network commands are refused today and will move into a multi-step approval tier as the safety model matures. All local file/command paths are confined to the configured Nodechat workspace (`C:\Users\bmoor\Local_AI` under the Windows launcher).

A small `NODECHAT_RUNTIME` system message is injected on every request so the model answers identity questions from the actual configured model and endpoint instead of inventing one.

## Default Backend

The validated vLLM backend is:

```text
model: Qwen/Qwen2.5-32B-Instruct-AWQ
endpoint on homelab: http://127.0.0.1:8000/v1
endpoint from LAN/Windows: http://192.168.1.198:8000/v1
```

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
/model [name]
/endpoint [url]
/system [text]
/history <query>
/pwd
/tree [path]
/read <path>
/search-files <query> [path]
/git-status
/web-search <query>
/web-fetch <url>
/web-open <url>
/propose-edit <path> :: <instruction>
/diff [all]
/apply [n|latest] [--check|--confirm]
/cmd <command>
/context
/clear-context
/status
/paste
```

`/paste` starts a multi-line prompt. End it with a single `.` on its own line.

## AI History Integration

AI History lookup is currently explicit. Auto-routing on prompts that clearly call for prior decisions or prior incidents is on the roadmap (see [`nodechat-scope.md`](nodechat-scope.md)); for now, use `/history` to inject a query result into the session.

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
NODECHAT_SESSION_ROOT
NODECHAT_WORKSPACE
NODECHAT_TEMPERATURE
NODECHAT_MAX_TOKENS
```

Windows launcher scripts:

```text
scripts/windows/nodechat.cmd
scripts/windows/nodechat-tunnel.cmd
```

`scripts/windows/nodechat.cmd` sets the default Nodechat workspace to the repo root (`C:\Users\bmoor\Local_AI`) so `/read`, `/tree`, `/search-files`, and `/git-status` work from the correct project even when the Command Prompt starts in `C:\Users\bmoor`.

## Local Context Tools

These tools add context blocks to the current session. The model sees only the injected output, not the whole filesystem.

```text
/pwd
/tree docs
/read docs\CURRENT_STATE.md
/search-files gpu2 docs
/git-status
```

Rules:

- `/read` is text-only and size-capped.
- `/tree` is depth/result capped.
- `/search-files` searches text files only and returns bounded filename/line matches.
- `/git-status` runs only the fixed read-only `git status --short --branch` command.
- Secret-ish paths and generated/private stores are refused rather than injected.

## Web Context Tools

Web fetch and search are currently invoked explicitly. Auto-routing for prompts that clearly call for fresh public data (upstream releases, CVEs, current pricing) is on the roadmap. Fetched text stays transient unless the user saves it.

```text
/web-search qwen2.5 awq vllm
/web-fetch https://example.com
/web-open https://example.com
```

`/web-search` uses DuckDuckGo HTML results and stores titles/URLs as leads. Use `/web-fetch` or `/web-open` on a result before treating the source text as evidence.

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
- Logged events include queued approvals, rejected approvals, approved command execution/blocking, refused commands, read-only command execution, `/apply --check`, and `/apply --confirm`.
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

## Capability Lanes

Capability is governed by risk tier, not by explicit-only-everything. See [`nodechat-scope.md`](nodechat-scope.md) for the tier definitions (Observe / Analyze / Prepare / Mutate / Dangerous) and the auto-routing roadmap. This section tracks what is implemented per capability lane.

### Observe lane (Done)

```text
chat with local vLLM (streaming, sessioned, slash-command UX)
/history <query>           AI History KB injection
/read <path>               text-only, size-capped
/tree [path]               depth/result capped
/search-files <q> [path]   text files only
/git-status                fixed `git status --short --branch`
/pwd
/web-search <query>        DuckDuckGo HTML, leads only
/web-fetch <url>           bounded text fetch
/web-open <url>            same as fetch but opens in session view
/cmd <read-only command>   allowlisted: git read subcommands, rg, dir/ls, type/cat, pwd, --version
```

Today every Observe-tier source is invoked explicitly. The roadmap is auto-routing with disclosed provenance.

### Prepare lane (Done)

```text
/propose-edit <path> :: <instruction>   single-file unified-diff proposal, stored in session
/diff [all]                             print latest or all stored proposals
/apply --check                          validate stored proposal against current file, no write
```

`/propose-edit` strips outer Markdown code fences before storing. `/apply --check` refuses ambiguous repeated hunks rather than fuzzy-applying the first match.

### Mutate lane (Partial)

```text
/apply [n|latest] --confirm    write backup, then apply stored proposal
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

Gaps in this lane: `/undo-apply <id|latest>` (backups exist, undo path does not yet), broader command classes beyond the current Git approval set, and live-node operator mutations (`docker restart`, `systemctl restart`) gated by tier.

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
