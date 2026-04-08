# Documentation Architecture (Revised)

Adapted from MealMastery's layered system. Designed for AI agent continuity with bounded growth and explicit maintenance.

## Design Principles

1. **Active vs cold storage** - Everything stays, but only the active layer is in the agent's reading path
2. **Bounded growth** - Every active document has a structural cap or expiration trigger
3. **Single source per volatile fact** - Component status, budget numbers, and other fast-changing data live in CURRENT_STATE.md only
4. **Maintenance is a task, not a side effect** - Monthly /maintain sessions handle curation; agents doing feature work only fix what they directly touch
5. **Archive, never delete** - Stale content moves to docs/archives/, recoverable if needed

## The Active Layer (read by agents every session)

| File | Purpose | Cap/Constraint |
|------|---------|---------------|
| CLAUDE.md | Rules, patterns, decisions, gotchas, session protocol | Stable content only. Nothing that changes more than monthly. |
| ATTITUDE.md | Behavioral constraints | Stable. Rarely changes. |
| SCRATCH.md | Session working memory | Cleared at session start. Append-only during session. |
| CURRENT_STATE.md | Pure snapshot of project right now | No history. Single source for all volatile facts. |
| SESSION_LOG.md | Recent session history | Current month only. Older months archived. |
| MEMORY.md (private) | Rules not yet promoted to CLAUDE.md | Capped at 200 lines. Rules only, no narratives. |

## The Warm Layer (read on demand, not every session)

| File | Purpose | When to read |
|------|---------|-------------|
| docs/HANDOVER_*.md | Active feature bridges | When picking up unfinished work. Has status + expiration condition. |
| docs/wiki/ (authored) | Decisions, rationale, research - not code-derivable | When working in that domain. Tagged type: authored. |
| docs/architecture/ | System architecture, hardware spec, software stack | When planning or building. |
| docs/AGENT_COORDINATION.md | Multi-agent rules | When parallel agents are running. |

## The Cold Layer (never read by agents, preserved for recovery)

| Location | Contents |
|----------|----------|
| docs/archives/SESSION_LOG_YYYY-MM.md | Monthly session log archives |
| docs/archives/handovers/ | Completed handover docs |

## Key Differences From Original Design

1. **CURRENT_STATE.md** - Pure present tense. No history, no changelog. Just what's true right now.
2. **SESSION_LOG.md** - Capped at current month. Previous months archived.
3. **MEMORY.md** - Rules-only format (rule + one-line rationale), not incident narratives. Rules proven across 3+ sessions promote to CLAUDE.md and get removed from MEMORY.md.
4. **Handovers** - Each has Status (IN PROGRESS | COMPLETE) and "Expires when:" header. Completed handovers move to archives. No index file - `ls docs/HANDOVER_*.md` is the index.
5. **Archives** - Cold storage for everything that ages out of active path.
6. **Wiki type tags** - Articles tagged `type: authored` (human judgment, maintained) vs `type: generated` (code-derivable, not maintained). Currently all articles are authored.
7. **/maintain protocol** - Dedicated monthly cleanup task. Not a side effect of feature work.

## Flows

### Normal Session:
```
Start: CLAUDE.md (auto) → ATTITUDE.md → SCRATCH.md → SESSION_LOG.md (top entries)
Work:  Write to SCRATCH.md. If volatile state changes, update CURRENT_STATE.md.
       If you notice a wrong fact in a doc you're reading, fix it.
End:   Append to SESSION_LOG.md. Update CURRENT_STATE.md.
```

### After User Correction:
Write the RULE (not the story) to MEMORY.md. One line + one-line rationale.

### After Completing a Handover:
Move handover to docs/archives/handovers/. Update CURRENT_STATE.md.

### Monthly /maintain:
Archive, promote, prune. No feature work.

### Research Intake (Karpathy Pipeline):
```
Source found → raw/source-name.md (using INTAKE_TEMPLATE) → wiki article compiled → indexes updated
```
