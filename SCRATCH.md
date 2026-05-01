# Session Scratch - 2026-05-01
Focus: Repo cleanup and repo-truth realignment.

## Observed
- `CLAUDE.md` was stale against current repo posture: it still listed Proxmox in the settled day-one stack.
- `docs/CURRENT_STATE.md` was stale against `docs/SESSION_LOG.md`: the repo had already recorded a safe bench-power checkpoint, but current state still described only inspection-stage progress.
- `docs/HANDOVER_ASSEMBLY.md` contradicted the newer serving posture by stating TP=3 would not work, while the rest of the repo treats it as a validation target, not a solved assumption.
- `SCRATCH.md` still reflected 2026-04-07 sourcing work instead of the current session.
- `docs/SESSION_LOG.md` still contained April entries even though the repo's own rule says the current-month file should be capped to the current month.

## Not Proved
- Any newer physical hardware state beyond what the repo itself records.
- Any current in-chassis cabling, switch state, BMC state, or successful POST.

## Cleanup Decisions
- Clean only contradictions and stale repo state proved from files in this checkout.
- Ignore Word lockfiles only; do not assume the untracked `.docx` note file should be deleted or ignored.
