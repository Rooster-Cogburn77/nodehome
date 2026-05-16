# Agent Evaluation Format Collapse

**Status:** Watch lane  
**Last updated:** 2026-05-16

This page tracks cases where frontier AI agents degrade or break the meaning of open evaluation formats. The core Nodehome lesson is not that a specific game or leaderboard is literally gone. The lesson is that open scoreboards become weak evidence once participants can run large-scale agent orchestration with unequal model budgets.

## Why This Matters For Nodehome

Nodechat is moving toward a local agentic terminal environment with tool use, provenance, audit, web context, live-node checks, and approval-gated mutation. That means any future evaluation of "agent skill" must record:

- Model/profile used.
- Tooling available.
- Context retrieved.
- Commands executed.
- Wall-clock time.
- Token/cost budget.
- Human interventions.
- Evidence/provenance used in the final answer.

Without that metadata, a scoreboard mostly measures willingness and ability to spend on orchestration, not clean underlying skill.

Nodechat already has the substrate this lesson requires:

- Per-turn `model_dispatched` audit rows record profile, model, endpoint, latency, prompt size, response size, and remote-cost estimates when applicable.
- Auto-routed context blocks carry source labels and provenance for history, repo, web, live, and model routing.
- Approved commands record the proposed argv, executed argv, exit code, resolved executable, output digest, and approval id.
- Live mutations split queued versus executed events, so "approval requested" and "mutation actually happened" are separate facts.

If a cyber-tooling lane is added later, it should inherit this plumbing instead of inventing a separate evidence trail.

## Required Internal Evaluation Tracks

Do not mix these tracks in Nodehome capability evals:

| Track | Meaning | Allowed context/tools | Question answered |
|-------|---------|-----------------------|-------------------|
| Pure | Model alone | Configured profile only; no tools, no auto-routing, no AI History | How capable is the raw model? |
| Augmented | Realistic Nodechat operator mode | Model plus Nodechat auto-routing for AI History, repo, web, live, and normal disclosure/audit | How capable is Nodechat as actually used? |
| Orchestrated | Outer-loop agent mode | Model plus Nodechat tools plus per-task dispatch/orchestration loop | How capable is the full agent system under a fixed budget? |

These are three different numbers. Mixing them produces the same kind of contaminated scoreboard the CTF post is warning about.

## Capability Claim Intake Schema

Any future sweep/digest/model-eval item that makes an AI capability claim should carry these fields before being treated as confirmed:

- `track`: `pure`, `augmented`, or `orchestrated`.
- `model`: exact model/profile, including remote/local provider when known.
- `tooling`: vanilla chat, Claude Code, Codex, Nodechat, custom orchestrator, CTFd API harness, etc.
- `time_budget`: wall-clock budget or event duration.
- `cost_budget`: token/API/GPU budget if known.
- `rules`: anti-AI, AI-allowed, AI-required, unknown, or unenforced.
- `evidence`: prompt/solve transcript, command log, scoreboard link, reproduction, or only anecdote.

Claims missing the track/tooling/budget/rules fields should be tagged `unverifiable-capability`, not `capability-confirmed`.

## Watch Entry: The CTF Scene Is Dead

- **Source:** kabir.au blog (primary, credentialed practitioner)
- **Link:** https://kabir.au/blog/the-ctf-scene-is-dead
- **Published:** 2026-05-01
- **Confidence:** primary-opinion. First-person, credentialed, and specific, but the strongest frontier-model capability claims are anecdotal rather than benchmarked in the post.
- **Novelty:** Frontier LLM agents, Claude-Code-style CLI tooling, and CTFd API orchestration reportedly make most medium CTF challenges and many hard challenges agent-solvable. The author argues open CTF scoreboards have shifted from measuring security skill to measuring AI orchestration plus token budget.
- **Action:** Watch lane. No Nodehome stack decision hinges on this. Borrow two patterns: per-task agent dispatch with bounded time, and explicit separation between human-only, AI-assisted, and fully agentic evaluation tracks.
- **Why it matters:** Concrete real-world signal on frontier-model end-to-end task capability in a security domain, plus a practical operator architecture pattern: dispatch one agent per challenge, let them run for a fixed window, then spend human attention on leftovers. It also warns that recruiting or benchmarking from open CTF leaderboard performance is becoming noisy.

## Calibration

The headline is intentionally dramatic. The narrower diagnosis is the useful part:

- Open online CTF scoreboards are no longer clean pure-human-skill measures.
- The underlying learning community, challenge craft, and lab value are not automatically dead.
- The strongest claim, that GPT-5.5 Pro can one-shot some Insane active leakless heap pwn challenges, should be treated as one operator's experience until independently reproduced.
- Claims about specialized cybersecurity models becoming less relevant than general frontier models are directional and plausible, but not quantified in the post.

## Nodehome Implications

- Treat CTFs as lab/training material, not as clean public evidence of human or agent skill.
- Do not evaluate Nodechat security capability by unsourced "CTF solved" claims.
- If security tooling enters Nodechat later, require solve-path provenance: prompts, retrieved context, tools, commands, model profile, elapsed time, and final reasoning.
- Do not mix human-only, AI-assisted, and full-agent orchestration results in one leaderboard.
- Internal capability evals should include fixed model budgets and visible audit logs, or they will reproduce the same format-collapse problem.

## Related Watch Items

- `docs/wiki/research/ai-agent-traps.md` - agent threat model and human-supervisor failure modes.
- `docs/wiki/research/memory-architectures.md` - model-internal memory watch lane and benchmark framing.
- `docs/runbooks/nodechat-scope.md` - Nodechat's capability-with-evidence and risk-tier model.
