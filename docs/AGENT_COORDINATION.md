# Agent Coordination Rules

Rules for when multiple AI agents work on the same project simultaneously or across sessions.

## Shared vs Owned Files

### Shared (Read by All, Written Carefully)
- **CLAUDE.md** - Only update if build spec or hard rules change
- **SCRATCH.md** - Current session owner only. Clear at session start.
- **docs/CURRENT_STATE.md** - Update after milestones
- **docs/SESSION_LOG.md** - Append only, never edit previous entries
- **memory/MEMORY.md** - Append lessons learned, keep under 200 lines

### Owned (One Agent at a Time)
- **HANDOVER_*.md** - Created by the agent doing the work
- **wiki/** articles - Any agent can create, but don't edit another agent's article without reading it first
- **architecture/** docs - Update only when hardware or software spec actually changes

## Communication Protocol

### Between Sessions
1. Outgoing agent updates SESSION_LOG.md with what was done and what's next
2. Outgoing agent updates CURRENT_STATE.md with project snapshot
3. Incoming agent reads CLAUDE.md → SCRATCH.md → SESSION_LOG.md (latest entry)

### After Compaction (Same Session)
1. Read SCRATCH.md to restore context
2. Read CURRENT_STATE.md if SCRATCH.md is insufficient
3. Continue work

### Conflict Resolution
- If two sources disagree, CLAUDE.md is the source of truth for specs and rules
- If SCRATCH.md conflicts with CURRENT_STATE.md, SCRATCH.md is more recent (it's the active session)
- If memory/MEMORY.md conflicts with CLAUDE.md, CLAUDE.md wins (MEMORY.md is supplementary)

## Multi-Agent Parallel Work
Not currently applicable (single-agent workflow). When the Sovereign Node is running local models for multi-agent tasks, revisit this doc to define:
- Which agent owns which files
- Git branching strategy
- Merge conflict resolution
- Shared state management
