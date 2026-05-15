# Nodechat Terminal Client

Status: initial local terminal chat client, no autonomous shell tools.

`scripts/nodechat.py` is a small stdlib-only terminal client for talking to the Nodehome local model stack through an OpenAI-compatible endpoint such as vLLM. It is meant to mirror the useful feel of Codex/Claude Code: terminal-first, sessioned, slash-command driven, and project-context aware.

It is not yet a coding agent. It does not execute shell commands, read files, edit files, or run tools inside the chat. That boundary is intentional until the approval and sandbox model is designed.

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
NODECHAT_TEMPERATURE
NODECHAT_MAX_TOKENS
```

Windows launcher scripts:

```text
scripts/windows/nodechat.cmd
scripts/windows/nodechat-tunnel.cmd
```

## Safety Boundary

Nodechat v0 has no shell tools. Future tool support should be added in this order:

1. Read-only local status commands.
2. Read-only repo inspection commands.
3. Gated write/edit commands with explicit approval.
4. Never unrestricted shell by default.

The point is to get a reliable terminal chat surface first, then add agent behavior deliberately.
