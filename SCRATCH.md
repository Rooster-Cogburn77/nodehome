# Session Scratch - 2026-05-10 (Session 15)
Focus: Operational hardening — service persistence, reboot validation, health-check tooling, IPMI runbook, system-enforced pigtail rule. Closed with a clean overnight power-down.

## Observed (validated this session)
- Both Docker containers (`vllm-server`, `open-webui`) updated to `--restart unless-stopped`. `docker inspect` confirms `RestartPolicy.Name = unless-stopped` on both.
- Full `sudo reboot` recovery validated end-to-end. Post-reboot: 3 GPUs back, Ollama service auto-active, both containers `Up`, Ollama API serving 5 models, Open WebUI HTTP 200, vLLM API ready after `~95 s` warmup (boot 04:36:12 → "Application startup complete" 04:37:50).
- `scripts/healthcheck.sh` written and stabilized through two real bug fixes:
  - BMC MAC parsing: `awk -F:` was splitting on every colon in the MAC; fixed with `-F': '`.
  - Docker container probes were unconditionally using `sudo -n docker`; failed silently for users in the docker group. Fixed by trying plain `docker` first, falling back to `sudo -n` only if needed.
  - Final pass on the healthy stack: `[HEALTHY] 2 warning(s)` for the two expected items (BMC LAN port unpatched, one historical `__warn_thunk` kernel line).
- `docs/runbooks/ipmi-recovery.md` authored. Captures BMC firmware `01.05.02`, dedicated NIC MAC `90:5a:08:7b:71:6d` (verified via `ipmitool lan print 1`, supersedes a one-character typo in the April archive), recovered factory default ADMIN password `SYZIFLTPAK` from `docs/archives/SESSION_LOG_2026-04.md:57`, web UI / `ipmitool` access procedures, failure scenarios addressed and not addressed, and a hardening note that the factory password is in repo git history and must be rotated before the BMC sees any LAN.
- **Pigtail rule violation discovered + fixed.** Healthcheck output flagged GPU 2 at `135.93 W / 6446 MiB / PCIe gen 4 active`. Root cause: an Open WebUI chat hit Ollama, Ollama saw GPUs 0+1 memory-loaded by vLLM, used its "least-loaded GPU" scheduler, and put the model on GPU 2. The temporary pigtail rule prohibits sustained load on GPU 2 — but the rule was operator-enforced, not system-enforced. Touch-checked the cable, restarted Ollama to evict the model (memory dropped to `1 MiB`, power to `33 W`).
- Pigtail rule is now **system-enforced on the Ollama side**. Extended `/etc/systemd/system/ollama.service.d/override.conf` to set `CUDA_VISIBLE_DEVICES=0,1` in addition to `OLLAMA_HOST=0.0.0.0:11434`. After `daemon-reload + systemctl restart ollama`, Ollama only sees 2 GPUs and physically cannot schedule anything on GPU 2 regardless of load. vLLM was already explicitly bound to `--gpus '"device=0,1"'`, so it was already correct.

## Decisions made this session
- vLLM and Open WebUI containers should be persistent across reboots (`--restart unless-stopped`).
- Pigtail rule enforcement moves from "operator-enforced documentation" to "system-enforced systemd env var" on the Ollama side. This is the right belt-and-suspenders posture; the documentation rule still applies for any other tool that might schedule work on GPU 2.
- Healthcheck script is read-only by design; warnings do not gate the exit code, only failures do. Good fit for both interactive use today and an eventual cron-driven automated periodic healthcheck after sudoers NOPASSWD is configured for the specific commands.

## Open trade-off introduced by the pigtail pin (deferred for next session decision)
- vLLM at `--gpu-memory-utilization 0.85` leaves ~2 GiB free per card on GPUs 0 and 1.
- With Ollama now restricted to those two cards, none of the locally-installed Ollama models fit in that headroom.
- Open WebUI chat through Ollama will fail to load any model while vLLM is running.
- Three forward options on the table:
  - **A.** Lower vLLM `--gpu-memory-utilization` to ~0.55 so GPUs 0+1 have ~10 GiB free each. Smaller KV cache for vLLM but Ollama gets headroom for 24B-class models.
  - **B.** Stop the vLLM container when not actively benchmarking. Loses always-on multi-GPU posture.
  - **C.** Point Open WebUI at the vLLM OpenAI-compatible endpoint as a second connection. Chat routes to vLLM's loaded model directly. Loses Ollama model-switching menu while vLLM is up.
- Decision deferred until the user picks an end-state preference.

## Not Proved (still ahead of the build)
- Sustained 3-GPU heavy inference. Gated on the cable arriving and the pigtail being retired.
- vLLM TP=3 on a 70B-class AWQ model (`Qwen/Qwen2.5-72B-Instruct-AWQ` is the planned target).
- 70B Q6 across all 3 GPUs.
- Sustained thermal validation under multi-hour load.
- ReBAR enable + A/B vs current `[Disabled]`.
- Sweep pipeline running natively on the server (still runs on laptop via Windows Task Scheduler).
- Final physical deployment: rack-mount on the Tedgetal shelf, dedicated IPMI ethernet patch, permanent location move.

## Live status of major services at end of session
- `ollama.service` — active, bound to `0.0.0.0:11434`, `CUDA_VISIBLE_DEVICES=0,1`
- `docker.service` — active, with `nvidia` runtime registered
- `vllm-server` container — `Up`, port `8000`, `Qwen/Qwen2.5-32B-Instruct-AWQ` on TP=2
- `open-webui` container — `Up`, port `3000`, healthy
- BMC — reachable in-band via USB-NIC at `169.254.3.1/24`. Dedicated IPMI port still unpatched (`IP Address: 0.0.0.0`).
- Host clean shutdown performed at end of session. Next start expects all services to auto-recover; healthcheck script is the validation tool.

## Next physical step
- Tedgetal sliding shelf arriving 2026-05-10. Rack-mount + dedicated IPMI patch + permanent location move are unblocked by the shelf and do **not** need the GPU 3 cable; the pigtail config is stable for the move and the cable swap is a separate 5-min operation when it arrives.
- The GPU 3 PCIe modular cable from `lizzieb753` UK is still in transit, realistic window `2026-05-23 to 2026-06-10`. Continuing to look for a faster source.

## Next software step
- Resolve the open A/B/C trade-off so Open WebUI chat works alongside vLLM.
- Then options on the queue: multi-prompt benchmark across all 5 models, sweep migration to server (shadow mode), `claw-code` install, code-task model bench with tool use, ReBAR A/B (post-cable), TP=3 + 70B AWQ (post-cable).

## Operational lessons from this session (already saved as memory files)
- Search the repo's archives, runbooks, and session logs before asking the user to physically retrieve information that may already be recorded. The BMC default password was already in `docs/archives/SESSION_LOG_2026-04.md:57`.
- Don't quote glib safety thresholds for cross-vendor hardware. Real safety depends on too many factors that aren't well-characterized for a specific stack. Frame by use category instead.
- Quote landed cost (item + shipping + import + tax), not "item + shipping," for cross-border purchases.
- Don't recommend stopping for the day or comment on time of day. The user sets pacing.
- When a long shell paste involves a heredoc, packed into a single quoted variable instead — terminal-side leading-space wraps break heredoc terminator matching.
- When the user describes a hardware setup, parse what they actually proposed before objecting to a worst-case interpretation of the keyword.
