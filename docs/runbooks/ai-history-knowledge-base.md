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
AI_HISTORY_HOST=0.0.0.0
AI_HISTORY_PORT=8765
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

Search quality notes:

- Queries are FTS-backed, then reranked in Python.
- Broad terms such as `vllm` and `ollama` are lower-weighted than local-decision terms such as `gpu2`, `pigtail`, `openwebui`, `powercap`, and `superflower`.
- Phrase aliases normalize common project terms: `Open WebUI` -> `openwebui`, `Super Flower` -> `superflower`, `power cap` -> `powercap`, and `GPU 2` / `GPU #2` -> `gpu2`.
- Aliases live in a separate FTS column so they affect matching/ranking without appearing in snippets.
- Results preserve source labels and line references even after reranking.

## Prompt Resource Mode

For a local model or agent, use prompt mode:

```bash
python3 ~/nodehome/scripts/ai_history_kb.py context "what did we decide about gpu2" --prompt
```

The output is designed to be injected into a model prompt as private reference context. The model should treat it as local project memory, not world knowledge.

## HTTP API

Start the host service manually:

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

Use this as an optional tool, not as always-on memory.

Repo-owned Open WebUI tool file:

```bash
scripts/openwebui/ai_history_tool.py
```

Install the persistent host API service.

Optional but recommended before install: bind to Docker's host bridge and set a bearer token. On most Docker installs the bridge is `172.17.0.1`; verify with `ip -4 addr show docker0`.

```bash
mkdir -p ~/node-private/chat-exports
openssl rand -hex 32
```

Put the generated token in:

```bash
nano ~/node-private/chat-exports/ai-history-kb.env
```

Example env file:

```text
AI_HISTORY_HOST=172.17.0.1
AI_HISTORY_PORT=8765
AI_HISTORY_TOKEN=paste-generated-token-here
```

Then install:

```bash
sudo cp ~/nodehome/scripts/systemd/ai-history-kb.service /etc/systemd/system/ai-history-kb.service
sudo systemctl daemon-reload
sudo systemctl enable --now ai-history-kb.service
systemctl status ai-history-kb.service --no-pager
```

Test from the host:

```bash
set -a
. ~/node-private/chat-exports/ai-history-kb.env
set +a
curl -H "Authorization: Bearer ${AI_HISTORY_TOKEN}" "http://${AI_HISTORY_HOST}:${AI_HISTORY_PORT}/health"
```

Security note: the service must be reachable from the Open WebUI Docker container through `host.docker.internal`. Prefer binding to the Docker bridge address plus `AI_HISTORY_TOKEN`. Use `0.0.0.0` only on a trusted LAN, and do not expose this service to the internet.

Open WebUI setup:

1. Open `http://192.168.1.198:3000`.
2. Go to `Workspace -> Tools`.
3. Create a new tool.
4. Paste the contents of `~/nodehome/scripts/openwebui/ai_history_tool.py`.
5. Save it as `Nodehome AI History`.
6. Open the tool's valves/settings.
7. Set `endpoint` to `http://host.docker.internal:8765`.
8. Set `token` to the same value as `AI_HISTORY_TOKEN` if configured.
9. Attach the tool to the target model from `Workspace -> Models -> <model> -> Tools`.
10. Ensure Function Calling is set to `Native`, not legacy Default mode.

Recommended system prompt addition for any model with this tool enabled:

```text
You have access to a private Nodehome AI History tool. Use it only when the user asks about prior decisions, previous work, handovers, current project state, or named local systems such as Nodehome, Local_AI, MealMastery, GPU2, vLLM, Ollama, Open WebUI, power caps, pigtail rules, or Walmart order history. Do not call it for general world knowledge.

When the tool returns HISTORY_CONTEXT, first apply its PROJECT_CONTEXT_CONTRACT. Resolve known project aliases before interpreting snippets, prefer durable/current-state snippets over older chat speculation when they conflict, preserve source provenance, and say when the retrieved history is incomplete, stale, or conflicting.

Canonical Nodehome aliases: GPU0 = NVIDIA index 0 = physical GPU #1 = bus 81:00.0. GPU1 = NVIDIA index 1 = physical GPU #2 = bus C1:00.0. GPU2 = NVIDIA index 2 = physical GPU #3 = bus C2:00.0 = pigtail-fed restricted card. vLLM sustained workloads currently use GPU0/GPU1 only. Ollama is restricted to CUDA_VISIBLE_DEVICES=0,1 while the pigtail rule is active. The 300 W power cap applies to GPU0/GPU1 only. The temporary pigtail rule retires only after the proper SF-1600F14HT PCIe cable is installed.
```

Operational model:

1. Keep vLLM serving normal model inference.
2. Keep `ai-history-kb.service` running on the host.
3. Keep the Open WebUI tool pointed at `http://host.docker.internal:8765`.
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
