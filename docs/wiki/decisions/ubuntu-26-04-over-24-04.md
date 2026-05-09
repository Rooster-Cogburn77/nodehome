# Decision: Ubuntu Server 26.04 LTS Over 24.04 LTS

**Date:** 2026-05-09
**Type:** authored
**Status:** Final

## Decision
Day-one OS target moves from `Ubuntu Server 24.04 LTS (Noble Numbat)` to `Ubuntu Server 26.04 LTS (Resolute Raccoon)`. The decision was made before the first installer USB was flashed, so no rollback work is required.

## Why
The user's stated goal for this build is "install once, run long-term without frequent OS upgrades." With that goal, 26.04 is the better target.

| Factor | 24.04.4 LTS | 26.04 LTS |
|---|---|---|
| Standard support ends | April 2029 | April 2031 |
| ESM / Ubuntu Pro support ends | April 2034 | April 2036 |
| Standard support remaining as of 2026-05-09 | ~3 years | ~5 years |
| In-place upgrade work to reach the next LTS | `do-release-upgrade` to 26.04 in roughly 2 years | None — already on the newest LTS |
| Kernel | 6.x | Linux 7.0 |

The "26.04 just released" risk is real for bleeding-edge GPUs (Blackwell), where proprietary driver maturity lags by 1-2 months. It is **not** a real risk for RTX 3090: GA102 / Ampere is 2020-era silicon, fully baked in current driver branches. Linux 7.0 may actually offer better PCIe / IOMMU handling on the EPYC + H12SSL-i platform than 6.x, not worse.

## Why Not 24.04
- 24.04 is the conservative "known-good" choice but the only durable advantage it has over 26.04 is "two months of extra real-world driver shake-out." Against a 5-year deployment, that advantage is small.
- Choosing 24.04 now means doing an in-place release upgrade in ~2 years anyway. Doing it during initial install costs nothing; doing it later risks production data and uptime.

## Why Not 22.04
- Older kernel, requires HWE for optimal EPYC support, less standard support window remaining. No reason to pick it for a 2026 build.

## Why Not Non-LTS / 25.10
- Non-LTS releases give 9 months of standard support. That contradicts the "install once, leave it alone" goal.

## Alternatives Considered
| OS | Standard Support | Pro / ESM | Kernel | Verdict |
|---|---|---|---|---|
| Ubuntu Server 22.04 LTS | until April 2027 | until April 2032 | 5.15 (HWE 6.x) | Older, less runway, no real upside |
| Ubuntu Server 24.04 LTS | until April 2029 | until April 2034 | 6.8 | Solid but shorter support window than 26.04 |
| Ubuntu Server 26.04 LTS | until April 2031 | until April 2036 | 7.0 | **Chosen** |
| Ubuntu Server 25.10 (interim) | until July 2026 | n/a | newer than 24.04 | Rejected — too short a support window |

## Stack Pin Posture
The day-one Ollama and vLLM pins (`Ollama v0.21.2`, `vLLM v0.19.1`) are not OS-version-coupled. Both are userspace and almost certainly run unchanged on 26.04. Treat their relationship to 26.04 as **verification**, not re-architecture: install them per the existing plan, confirm they run, and only revisit the pins if a real 26.04-specific issue appears.

## Rollback Plan
If 26.04 produces an unrecoverable bring-up issue with the H12SSL-i + 3x RTX 3090 stack, fall back to Ubuntu Server 24.04.4 LTS using the same install procedure (UEFI USB → install onto `BLK0`). 24.04 is still actively supported and is a known-safe target. Document any rollback in `docs/SESSION_LOG.md` and update this decision to `Status: Reversed` with a short reason.
