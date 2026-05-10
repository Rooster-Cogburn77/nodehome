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
- **Option C landed.** Open WebUI Admin Panel → Settings → Connections → added an OpenAI API entry with URL `http://host.docker.internal:8000/v1`, key `local`, prefix ID `vllm`. Verify went green and pulled `Qwen/Qwen2.5-32B-Instruct-AWQ` from the vLLM container. Model picker in chat now shows `vllm.Qwen/Qwen2.5-32B-Instruct-AWQ` alongside the Ollama models. Real prompt got a coherent reply through the vLLM path; user observed it as "really fast" subjectively (matches the Session 14 benchmark of 59.13 tok/s vs 39.21 for Ollama on the same model class). Trade-off closed.
- Side fix: Qwen claimed it was "hosted by Alibaba Cloud" out of the box, which is just its pretraining identity. Set a per-model System Prompt in Open WebUI Workspace → Models that grounds it in this hardware (3x RTX 3090, EPYC 7302P, vLLM v0.19.1 container, no Alibaba Cloud connection). Same workspace-level system-prompt fix applies to the Ollama models if/when it matters.

## Live status of major services (post-rebuild, post-Option-C)
- `ollama.service` — active, API on `:11434` returning all 5 models (`gemma3:27b`, `mistral-small3.1:24b`, `qwen2.5:32b-instruct-q4_K_M`, `llama3.3:70b-instruct-q4_K_M`, `qwen3:8b`); none currently loaded into VRAM (vLLM owns it).
- `vllm-server` container — `Up`, port 8000, `/v1/models` returning 200, `Qwen/Qwen2.5-32B-Instruct-AWQ` resident on GPUs 0+1 at ~22 GiB each. Reachable both directly and through Open WebUI.
- Open WebUI container — `Up`, port 3000, both OpenAI-compatible (vLLM) and Ollama connections active in the model picker.
- nvidia-smi: GPU 0 22775 MiB, GPU 1 22472 MiB, GPU 2 1 MiB (pigtail rule respected).
- Permanent in-chassis wiring — done; cable management for permanent install completed.
- BMC — not re-verified this session post-rebuild. Dedicated IPMI port still unpatched.

## Immediate next steps
1. `./scripts/healthcheck.sh` — single-pass validation of host/GPUs/storage/Ollama/Docker/APIs/BMC/kernel for the post-rebuild + post-Option-C baseline.
2. Capture JF1 pinout into `docs/runbooks/h12ssl-i-front-panel.md` before the next chassis-open event.

## Still ahead (unchanged from Session 15)
- Cable for GPU #3 in transit, realistic window `2026-05-23 to 2026-06-10`.
- Rack-mount on Tedgetal sliding shelf, dedicated IPMI ethernet patch, permanent location move — unblocked by the shelf, blocked-by-preference on completing the cable swap first so the box is moved/cabled-into-rack only once.
- BMC hardening before LAN exposure: rotate factory `SYZIFLTPAK` (in repo git history), replace self-signed cert, set static IP. If "doing things the right way" is the bar, the BMC should sit on its own management VLAN, not the flat LAN.
- TP=3 + 70B-class AWQ benchmark, ReBAR A/B, sustained 3-GPU thermal soak — all post-cable.
- Sweeps pipeline migration to server (still on laptop via Task Scheduler).

## Operational lessons added this session
- "Don't suggest the easy/shortcut route" — saved as feedback memory. Default to the proper path; offering "you can skip this" reads as me trying to reduce my own work or hedging on the user's standards.
