# AI History Knowledge Base

Status: active local-history resource, first built on 2026-05-14.

This system turns exported Claude desktop/web chats, Codex sessions, and Claude Code sessions into one private searchable reference base. It is not general model memory. It is a project/history resource that local models or agents should query only when the user asks about prior decisions, project state, handovers, or named local topics.

## Purpose

- Preserve long-term working context across Claude, Codex, and Claude Code.
- Keep source provenance on every result.
- Avoid polluting model answers with irrelevant chat history.
- Support local-only lookup from the homelab node.

## Source Paths

Raw exports and generated indexes live outside the repo under `~/node-private`:

- Claude desktop/web raw export: `~/node-private/chat-exports/claude/raw/`
- Claude desktop/web extracted export: `~/node-private/chat-exports/claude/extracted/2026-05-14/`
- Claude desktop/web SQLite index: `~/node-private/chat-exports/claude/index/claude-2026-05-14.sqlite`
- Codex raw export: `~/node-private/chat-exports/codex/raw/`
- Codex extracted export: `~/node-private/chat-exports/codex/extracted/2026-05-14/`
- Codex SQLite index: `~/node-private/chat-exports/codex/index/codex-2026-05-14.sqlite`
- Claude Code raw export: `~/node-private/chat-exports/claude-code/raw/`
- Claude Code extracted export: `~/node-private/chat-exports/claude-code/extracted/2026-05-14/`
- Claude Code SQLite index: `~/node-private/chat-exports/claude-code/index/claude-code-2026-05-14.sqlite`
- Unified SQLite FTS index: `~/node-private/chat-exports/unified/index/ai-history-2026-05-14.sqlite`

Do not commit raw exports or SQLite indexes. They contain private chat history and may contain secrets or personal data.

## Repo Utility

The repo-owned utility is [scripts/ai_history_kb.py](../../scripts/ai_history_kb.py).

Index extracted source exports:

```bash
python3 ~/nodehome/scripts/ai_history_kb.py index-sources all
```

Compose the source-specific SQLite files into the unified knowledge base:

```bash
python3 ~/nodehome/scripts/ai_history_kb.py rebuild
```

Do both in one pass:

```bash
python3 ~/nodehome/scripts/ai_history_kb.py rebuild --index-sources
```

Useful environment overrides:

```bash
AI_HISTORY_ROOT=/home/bmoore_77/node-private/chat-exports
AI_HISTORY_SNAPSHOT=2026-05-14
AI_HISTORY_DB=/home/bmoore_77/node-private/chat-exports/unified/index/ai-history-2026-05-14.sqlite
AI_HISTORY_TOKEN=<optional bearer token for HTTP mode>
```

## Validation Commands

Run these on the homelab node:

```bash
python3 ~/nodehome/scripts/ai_history_kb.py status
python3 ~/nodehome/scripts/ai_history_kb.py doctor
python3 ~/nodehome/scripts/ai_history_kb.py search gpu2 --limit 5
python3 ~/nodehome/scripts/ai_history_kb.py search '"super flower"' --limit 5
python3 ~/nodehome/scripts/ai_history_kb.py context "what did we decide about gpu2" --limit 5
python3 ~/nodehome/scripts/ai_history_kb.py context "capital of france"
```

Expected behavior:

- `status` reports total rows and per-source counts.
- `doctor` runs `PRAGMA integrity_check` and validates `kb_items` versus `kb_fts` counts.
- `search gpu2` returns snippets with source labels such as `codex`, `claude-code`, or `claude-desktop`.
- `context "what did we decide about gpu2"` returns `HISTORY_CONTEXT`.
- `context "capital of france"` returns `NO_HISTORY_CONTEXT` unless forced, because that is not a project-history query.

## Context Router

The context command intentionally gates searches:

```bash
python3 ~/nodehome/scripts/ai_history_kb.py context "what did we decide about gpu2"
```

Returns history only when the query matches project-history triggers such as:

- `previous`
- `what did we`
- `decision`
- `current state`
- `nodehome`
- `gpu`
- `vllm`
- `open webui`
- `power cap`
- `pigtail`
- `super flower`
- `walmart`
- `claude`
- `codex`

For deliberate manual lookup, use:

```bash
python3 ~/nodehome/scripts/ai_history_kb.py context "capital of france" --force
```

## Prompt Resource Mode

For a local model or agent, use prompt mode:

```bash
python3 ~/nodehome/scripts/ai_history_kb.py context "what did we decide about gpu2" --prompt
```

The output is designed to be injected into a model prompt as private reference context. The model should treat it as local project memory, not world knowledge.

## HTTP API

Start the host-local service:

```bash
python3 ~/nodehome/scripts/ai_history_kb.py serve --host 127.0.0.1 --port 8765
```

If binding anywhere beyond host loopback, set `AI_HISTORY_TOKEN` or pass `--token`.

Health check:

```bash
curl http://127.0.0.1:8765/health
```

Context lookup:

```bash
curl -s http://127.0.0.1:8765/context -H 'Content-Type: application/json' -d '{"query":"what did we decide about gpu2","limit":5}'
```

Prompt-ready lookup:

```bash
curl -s http://127.0.0.1:8765/prompt -H 'Content-Type: application/json' -d '{"query":"what did we decide about gpu2","limit":5}'
```

## Open WebUI / vLLM Integration Plan

Use this as an optional tool, not as always-on memory:

1. Keep vLLM serving normal model inference.
2. Run `ai_history_kb.py serve`.
3. Add an Open WebUI tool/function that calls `/context` or `/prompt`.
4. Instruct the model to call the tool only when the user asks about prior project state, previous decisions, handovers, or named local systems.
5. Preserve provenance labels in the answer when using snippets.

Important network boundary: `--host 127.0.0.1` is safest for host-local testing, but the Open WebUI Docker container will not reach the host's loopback address through `host.docker.internal`. For container access, bind the service to the Docker bridge address or another explicitly firewalled local interface, set `AI_HISTORY_TOKEN`, then point the Open WebUI tool at that address. Do not expose this service broadly to the LAN.

This gives GPT/Claude-style memory behavior without making every answer search private history.

## Maintenance

Refresh cycle:

1. Export new Claude desktop/web, Codex, and Claude Code data.
2. Store raw exports under `~/node-private/chat-exports/<source>/raw/`.
3. Run `python3 ~/nodehome/scripts/ai_history_kb.py index-sources all --snapshot YYYY-MM-DD`.
4. Run `python3 ~/nodehome/scripts/ai_history_kb.py rebuild --snapshot YYYY-MM-DD`.
5. Run `python3 ~/nodehome/scripts/ai_history_kb.py doctor`.
6. Spot-check known queries before wiring the DB into model tooling.

Longer-term improvements:

- Add a stable `current.sqlite` symlink or environment variable for the active DB.
- Add embeddings and reranking for semantic recall.
- Add redaction checks before indexing future exports.
- Add an Open WebUI tool manifest once the local API is settled.
