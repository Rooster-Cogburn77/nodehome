# Locker vs Build Our Own Ingest Layer

**Date:** 2026-04-07  
**Status:** Considered, not committed

## Question

Would a self-hosted file platform like `Locker` be useful for Sovereign Node, or should we build our own narrower version?

## Short Answer

Potentially useful as a supporting service, not a core dependency.

`Locker` fits the "document inbox + canonical file store" role well, but it does **not** replace:
- model serving
- retrieval / vector indexing
- agent orchestration
- curated knowledge management

If the goal is a broader personal or small-team research appliance, `Locker` is worth keeping on the table. If the goal is a lean single-user local AI box, a custom lightweight file-ingest layer may be cleaner.

## Recommended Architecture

Use clear ownership boundaries:

- `Locker` or equivalent:
  Raw file ingress and durable storage for PDFs, screenshots, transcripts, exports, datasets, and uploads.
- `Obsidian`:
  Human-curated notes, synthesis, project pages, and wiki.
- `Ingest / RAG pipeline`:
  OCR, text extraction, chunking, metadata extraction, embeddings, and retrieval indexes.
- `Ollama` / `vLLM`:
  Local inference endpoints.

Working model:

`raw files -> file store -> ingest pipeline -> vector index`  
`human notes -> Obsidian -> ingest pipeline -> vector index`  
`agents/chat -> retrieval layer -> local model server`

## Design Rules

- Keep one source of truth for raw files.
- Keep one source of truth for curated notes.
- Treat embeddings and indexes as disposable cache, not primary storage.
- Link Obsidian notes back to stored files instead of duplicating binaries.
- Do not let agent outputs overwrite curated knowledge automatically.

## When Locker Makes Sense

- Need a cleaner upload/share UX than plain folders.
- Want multi-device or multi-user access to the same research corpus.
- Expect lots of PDFs, screenshots, and files from outside sources.
- Want a real "landing zone" before documents enter the knowledge workflow.

## When Building Our Own Makes More Sense

- Single-user setup.
- We only need local folders plus a narrow ingest API.
- We want tighter control over metadata, indexing triggers, and storage layout.
- We do not want another full web app to maintain.

## If We Build Our Own

Minimum useful scope:

- watched `inbox/` directory
- upload endpoint or simple local drop folder
- file metadata table
- extraction/OCR worker
- chunk + embedding pipeline
- links from extracted content to Obsidian notes
- search API for agents and chat

This would capture most of the value without adopting a separate product.

## Current Recommendation

Do **not** commit to `Locker` yet.

Keep the architecture pattern:
- canonical file store
- curated Obsidian vault
- separate ingest/index layer

Implementation can stay open:
- adopt `Locker` later if we want a polished file UX
- or build a narrower internal version once the Sovereign Node workflows are clearer
