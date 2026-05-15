# Nodechat Terminal Client

Status: validated terminal chat client with explicit read-only local context tools and explicit web fetch/search tools.

`scripts/nodechat.py` is a small stdlib-only terminal client for talking to the Nodehome local model stack through an OpenAI-compatible endpoint such as vLLM. It is meant to mirror the useful feel of Codex/Claude Code: terminal-first, sessioned, slash-command driven, and project-context aware.

It is not a write-capable coding agent. It can now inject explicitly requested read-only local context and explicitly requested web context into the chat. It still does not edit files, run arbitrary shell commands, browse automatically, or persist fetched web content unless the user explicitly saves it outside Nodechat.

It can also generate patch proposals with `/propose-edit`, but those proposals are stored only in the Nodechat session. Nodechat does not apply them to disk.

Nodechat can apply a stored proposal only through `/apply ... --confirm`. `/apply` validates the proposal first, writes a backup under the Nodechat session directory, and only supports bounded single-file text edits.

The client injects a small `NODECHAT_RUNTIME` system message on every request so the model can answer identity questions from the actual configured model and endpoint instead of inventing an identity.

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
/context
/clear-context
/status
/paste
```

`/paste` starts a multi-line prompt. End it with a single `.` on its own line.

## AI History Integration

AI History lookup is explicit. It does not run automatically.

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

Web access is explicit and transient:

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
- Applying a proposal is still manual/outside Nodechat until the later approval-gated write phase exists.
- `/apply --check` validates the latest proposal without writing.
- `/apply --confirm` applies the latest proposal after validation and writes a backup under `~/.nodehome/nodechat/backups/`.
- `/apply <n> --confirm` applies a specific proposal by its session index.

## Tool Roadmap

Decision captured 2026-05-15: Nodechat should grow toward a Codex/Claude Code style terminal experience, but in explicit phases. The model should never pretend it has file, shell, or internet access unless the corresponding command/tool exists and was used.

### Phase 0 - Done

Current capabilities:

```text
chat with local vLLM
persist sessions
slash-command UX
explicit AI History injection
Windows launchers
SSH tunnel path for private history
```

### Phase 1 - Explicit Read-Only Local Context

Implemented commands:

```text
/read <path>
/tree [path]
/search-files <query> [path]
/git-status
/pwd
```

Rules:

- Only read when the user explicitly asks.
- Print what was read or searched before injecting it.
- Cap file size and result count.
- Prefer repo/workspace paths; warn before reading secrets, env files, exports, or private data stores.
- Do not edit files in this phase.
- Block common private/generated paths such as `.nodehome`, `.ssh`, `.git`, `node-private`, `chat-exports`, `node_modules`, and likely key/token files.

### Phase 2 - Explicit Web Tools

Implemented commands:

```text
/web-search <query>
/web-open <url>
/web-fetch <url>
```

Rules:

- No automatic browsing.
- Web access only through explicit slash command or explicit user approval.
- Preserve source URLs in the injected context.
- Treat search snippets as leads, not proof.
- Keep fetched text transient unless the user explicitly saves it.
- Do not use web tools for private/local facts that should come from AI History or repo files.

### Phase 3 - Proposed Edits Only

Implemented commands:

```text
/propose-edit <path>
/diff
```

Rules:

- Generate patch/diff proposals only.
- No write to disk.
- User manually reviews/applies or approves moving to Phase 4 behavior.
- `/propose-edit` strips outer Markdown code fences from model output before storing the proposal.

### Phase 4 - Approval-Gated Writes

Implemented command:

```text
/apply
```

Rules:

- Show exact files affected.
- Require explicit confirmation before writing.
- Keep backups or diffs.
- Never write secrets to repo.
- Supports stored proposal diffs only; no freeform `/write <path>` exists.
- Refuses blocked private/generated paths and non-text file types.
- Validates the unified diff against the current file before writing.
- Writes backups outside the repo under the Nodechat session backup directory.

### Phase 5 - Approval-Gated Shell

Planned commands:

```text
/cmd <command>
/approve
```

Rules:

- No unrestricted shell by default.
- Classify commands as read-only, write, network, privileged, or destructive.
- Require explicit approval for write/network/privileged/destructive commands.
- Never auto-run destructive commands.
- Keep command output in the session log.

## Safety Boundary

Nodechat currently has explicit read-only file/context tools and explicit web fetch/search tools. It still has no write/edit tools and no arbitrary shell. Future tool support should continue in this order:

1. Read-only local context commands. Done.
2. Explicit web search/fetch commands. Done.
3. Proposed edit/diff commands with no writes. Done.
4. Gated write/edit commands with explicit approval. Partially done via `/apply`; no freeform `/write`.
5. Approval-gated shell, never unrestricted by default.

The point is to preserve a reliable terminal chat surface while adding agent behavior deliberately.
