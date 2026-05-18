# Ollama / vLLM Coexistence

Status: operational note for the current 2-GPU production posture.

## Current Posture

Ollama and vLLM are both installed, but they do not have equal access to GPU
memory during normal operation.

- `vllm-server` is the production multi-GPU lane: `Qwen/Qwen2.5-32B-Instruct-AWQ`
  on GPUs 0 and 1, tensor parallel size 2, `--gpu-memory-utilization 0.85`.
- Ollama is the convenience / single-GPU lane, but its systemd service is
  pinned to GPUs 0 and 1 with `CUDA_VISIBLE_DEVICES=0,1`.
- GPU 2 / physical GPU #3 stays excluded while the temporary pigtail rule is in
  force.
- Open WebUI exposes both paths. Use the `vllm.*` model when vLLM is running
  and a chat needs the production lane.

This means Ollama can be healthy while still being unable to load a large model
under the current resident vLLM memory pressure.

## Expected Failure Mode

When vLLM is already loaded at high GPU memory utilization, Ollama may fail to
place larger models or large-context requests on GPU 0/1. Expected symptoms:

- CUDA allocation failures in `journalctl -u ollama`
- Ollama layout backoff messages
- CPU fallback for model weights / KV cache
- very slow responses after CPU fallback
- runner termination such as `signal: killed`

Do not treat those symptoms by themselves as proof that Ollama is down, that
Nodechat `/live` failed, or that Open WebUI is broken. First separate service
health from model-load capacity.

## 2026-05-18 Evidence

After pulling homelab to commit `7a77d2b`, this one-shot Nodechat command ran
successfully on the node:

```bash
python3 scripts/nodechat.py --once "/live journal ollama"
```

Observed from the resulting `LIVE_NODE_STATUS` block:

- `check: journal ollama`
- `target: local`
- `command: journalctl -u ollama --no-pager -n 200`
- `exit_code: 0`
- newest-tail truncation preserved the recent journal entries

The journal showed older May 17 large-model pressure:

- CUDA OOM while allocating about `1447.50 MiB`
- layout backoff
- CPU fallback with `0/63` GPU layers for a `gemma3` load
- runner kills at `2026-05-17 18:38:18` and `2026-05-17 22:11:23`

After the May 18 reboot, Ollama started cleanly at `2026-05-18 03:37:33`,
reported version `0.23.2`, and discovered both visible RTX 3090s with about
`23.6 GiB` / `23.3 GiB` available VRAM before vLLM pressure returned.

Conclusion: the journal path and Ollama service were healthy. The issue was
large-context model-load pressure under constrained VRAM.

## Operator Rules

Use this decision tree before calling Ollama "broken":

1. Check service health:

```bash
systemctl is-active ollama
curl -s http://127.0.0.1:11434/api/tags | head
python3 scripts/nodechat.py --once "/live journal ollama"
```

2. Check whether vLLM is occupying GPUs 0/1:

```bash
nvidia-smi
docker ps --filter name=vllm-server
```

3. If vLLM is running and the prompt can use the production path, select the
   `vllm.Qwen/Qwen2.5-32B-Instruct-AWQ` model in Open WebUI or use the vLLM
   endpoint directly.

4. If the task specifically needs an Ollama model, intentionally free GPU memory
   first. The default fallback policy is Option B from Session 16: stop
   `vllm-server` for the Ollama-heavy task, then restart vLLM afterward. Do not
   lower vLLM's default memory utilization as a casual workaround; Option A was
   rejected because the high KV-cache headroom is the reason vLLM is running.

5. After any intentional stop/restart, verify the target path with `/live`,
   `/live logs vllm`, `/live journal ollama`, or a direct API smoke before
   declaring the stack recovered.

## What Counts As A Problem

Escalate if any of these happen:

- `systemctl is-active ollama` is not `active`
- `/api/tags` fails locally while the service is active
- `journalctl -u ollama` shows repeated crashes at idle with no model load
- vLLM and Ollama both fail after freeing GPU memory
- GPU 2 becomes visible to Ollama again while the pigtail rule is still active

Otherwise, treat CUDA OOM/backoff under vLLM residency as expected capacity
contention, not a service outage.
