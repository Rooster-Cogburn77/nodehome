# Sovereign Node - Session Log
<!-- Current month only. Archive previous months under docs/archives/SESSION_LOG_YYYY-MM.md -->

## 2026-05-01 (Session 7)
**Focus:** Repo cleanup and repo-truth realignment
**What was done:**
- Re-read the current repo state with zero trust toward prior handoff claims.
- Confirmed the worktree is still clean except for two untracked root files: `Home Build Progress Tracking doc_notes.docx` and its Word lockfile.
- Confirmed the latest verified repo commit remains `87a04c5`.
- Realigned stale docs that contradicted newer repo truth:
  - `CLAUDE.md` no longer lists Proxmox as part of the settled day-one stack.
  - `docs/CURRENT_STATE.md` now reflects the later safe bench-power checkpoint already recorded in the April log, while explicitly preserving that current in-chassis state and successful POST are still unproved from repo evidence.
  - `docs/HANDOVER_ASSEMBLY.md` now matches the newer serving posture: TP=3 is a validation target, not a universal guarantee or a blanket impossibility.
  - `SCRATCH.md` was reset to the current session and now records the cleanup scope and evidence boundary.
- Archived April session history into `docs/archives/SESSION_LOG_2026-04.md` and started a May log per the repo's own documentation-architecture rule.
- Added a narrow `.gitignore` rule for Word lockfiles (`~$*.docx`) without ignoring the actual untracked `.docx` note file.
**Commits:** Pending
**Next:** Verify the diff, then decide whether to leave the untracked `.docx` note outside git, add a repo-specific ignore for it, or remove it manually if it is no longer needed.

## 2026-05-05 (Session 8)
**Focus:** Hyperscaler capex recall and SubQ watch-state
**What was done:**
- Recovered the saved hyperscaler capex summary from the local wiki: `~$600B+/year` in 2026 and `~$1.3T` over 2024-2026, with the caveat that the repo stored a rolled-up conclusion rather than a filing-by-filing table.
- Re-checked the historical infrastructure comparison framing and corrected the old Interstate shorthand: the stored `~2x Interstate` line does not hold up cleanly and should be treated as stale until rebuilt with a single inflation-consistent table.
- Reviewed SubQ from primary vendor materials and classified it as a hosted long-context architecture watch item: interesting enough to track, but not a current local-node stack input.
- Logged that early access for SubQ was requested and that the current status is pending review/waitlist.
**Commits:** Pending
**Next:** If needed, replace the old hyperscaler historical comparison note with a clean inflation-consistent table and keep SubQ in the hosted-routing watch lane until independent validation improves.
