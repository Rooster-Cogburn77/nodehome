# Session Scratch - 2026-05-10 (Session 16)
Focus: Permanent in-chassis install — drive cage removal, front-panel header wiring, internal cable cleanup, GPU reinstall, power-on validation. Continuation of Session 15's same-day power-down.

## Reported / done this session
- All three left-side internal drive cage sections removed from the SilverStone RM400. Build is NVMe-only, so the cages were dead weight blocking cable routing and GPU-area access. Whole left-side bay area now open.
- Front-panel header (JF1) on the H12SSL-i wired to chassis FP leads. The board has an on-board power button so the chassis FP power button is redundant for bring-up — wired anyway because the build target is permanent install, not minimum-viable.
- Both chassis fans (front + rear) connected to motherboard fan headers.
- Top GPU removed during chassis work to gain access; reinstalled with the other two after wiring cleanup. All 3 GPUs back in their original slots.
- Internal wiring tidied for permanent install: front-panel wires routed against chassis edge, USB 3 cable kept clear of GPU/fan zone, fan leads secured, nothing under tension, no signal wires across PCIe slot faces.
- Host powered back on after rebuild. Initial smoke test: Open WebUI chat with `gemma3:27b` returned a coherent reply through the Ollama path (model loaded, Ollama service up, Open WebUI container up, at least one of GPU 0/1 had memory).

## Verified by me directly
- `git status` clean before this checkpoint, on `main`, up to date with `origin/main`.
- Open WebUI chat content showing `gemma3:27b` responding (user paste).
- That's it. Everything else in "Reported" above is from the user's narration of the codex-assisted chassis work; I did not personally see `nvidia-smi`, `docker ps`, or `healthcheck.sh` output post-rebuild yet.

## Operational signal worth flagging
- `gemma3:27b` is ~17 GB. For Ollama to load it on GPUs 0+1 (`CUDA_VISIBLE_DEVICES=0,1`), there had to be ~8-9 GB free per card at chat time. With vLLM at `--gpu-memory-utilization 0.85` it leaves only ~2 GiB free per card. So either the vLLM container did not auto-start after the rebuild, or it is up but unloaded. Needs `docker ps` + `nvidia-smi` to disambiguate.
- This is the same trade-off space recorded at end of Session 15 (the open A/B/C question). Whatever the actual current state is, it's a data point for picking between A/B/C.

## Documentation gap (follow-on)
- The JF1 pinout used for the FP wiring was not captured into a repo runbook. Per the project rule "Documentation First," the next time GPUs come out and the FP header has to be re-wired, the pinout should already be in repo. Action: when convenient, photograph the JF1 silkscreen on the H12SSL-i (or pull the page from the Supermicro manual at https://www.supermicro.com/manuals/motherboard/EPYC7000/MNL-2314.pdf) and write `docs/runbooks/h12ssl-i-front-panel.md`.

## Decisions standing (carried forward from Session 15)
- A/B/C trade-off resolution: **Option C primary, B fallback, A rejected.** Open WebUI gets a second OpenAI-compatible Connection pointing at the vLLM container (`http://host.docker.internal:8000/v1`) so chat routes to vLLM directly without forcing Ollama to share VRAM with vLLM. If vLLM is down for whatever reason, fallback is to stop the vLLM container entirely (Option B) and let Ollama use the full 24 GB per card. Lowering vLLM `--gpu-memory-utilization` to 0.55 (Option A) was rejected — the whole point of running vLLM is the higher KV-cache headroom, and giving that up just to satisfy Ollama is the wrong direction.
- Not yet implemented in the UI; that's the next action after this checkpoint.

## Live status of major services (best-effort, post-rebuild, not all directly verified)
- `ollama.service` — active, accepting requests on port 11434, gemma3:27b loaded successfully (verified via UI chat reply)
- Open WebUI container — up, port 3000, serving (verified via UI chat reply)
- `vllm-server` container — state TBD, see operational signal above
- Permanent in-chassis wiring — done (per user report); cable management for permanent install completed
- BMC — assumed reachable via USB-NIC at `169.254.3.1/24` per Session 15 state; not re-verified this session. Dedicated IPMI port still unpatched.

## Immediate next steps after this commit
1. `./scripts/healthcheck.sh` — single-pass validation of host/GPUs/storage/Ollama/Docker/APIs/BMC/kernel.
2. Disambiguate vLLM container state (`docker ps`, `docker logs vllm-server`, `nvidia-smi` for memory check).
3. Implement Option C: Open WebUI → Settings → Connections → add OpenAI-compatible endpoint, URL `http://host.docker.internal:8000/v1`, model picker should then show both Ollama and vLLM models.
4. Capture JF1 pinout into `docs/runbooks/h12ssl-i-front-panel.md` (low priority; before next chassis-open event).

## Still ahead (unchanged from Session 15)
- Cable for GPU #3 in transit, realistic window `2026-05-23 to 2026-06-10`.
- Rack-mount on Tedgetal sliding shelf, dedicated IPMI ethernet patch, permanent location move — unblocked by the shelf, blocked-by-preference on completing the cable swap first so the box is moved/cabled-into-rack only once.
- BMC hardening before LAN exposure: rotate factory `SYZIFLTPAK` (in repo git history), replace self-signed cert, set static IP. If "doing things the right way" is the bar, the BMC should sit on its own management VLAN, not the flat LAN.
- TP=3 + 70B-class AWQ benchmark, ReBAR A/B, sustained 3-GPU thermal soak — all post-cable.
- Sweeps pipeline migration to server (still on laptop via Task Scheduler).

## Operational lessons added this session
- "Don't suggest the easy/shortcut route" — saved as feedback memory. Default to the proper path; offering "you can skip this" reads as me trying to reduce my own work or hedging on the user's standards.
