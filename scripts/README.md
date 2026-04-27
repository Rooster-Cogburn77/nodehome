# Day-One Install Scripts

These scripts target a fresh Ubuntu 24.04 LTS bare-metal install for the Sovereign Node / Nodehome AI serving box.

## Main Bootstrap

Edit the tunables at the top of `bootstrap.sh` first:

- `HOSTNAME`
- `ADMIN_USER`
- `STATIC_IP_CIDR`
- `STATIC_GATEWAY`
- `STATIC_DNS`
- `NETPLAN_INTERFACE`
- `SSH_PUBLIC_KEY`
- `NVIDIA_DRIVER_PACKAGE`
- `CUDA_TOOLKIT_PACKAGE`
- `OLLAMA_TEST_MODEL`
- `VLLM_MODEL`
- `VLLM_TENSOR_PARALLEL_SIZE`
- `VLLM_CPU_OFFLOAD_GB`

Run:

```bash
sudo bash scripts/bootstrap.sh
```

The script installs/configures:

- Ubuntu base packages
- hostname `nodehome`
- optional static IP netplan file
- SSH hardening
- NVIDIA driver and CUDA toolkit
- Docker CE
- NVIDIA Container Toolkit
- Ollama bound to `0.0.0.0:11434`
- small Ollama test model
- vLLM Docker launch helper

## Day-One Serving Posture

- **Ollama first:** use it for the first working local inference path, smoke tests, convenience serving, and small/single-GPU models.
- **vLLM second:** use it for serious multi-GPU serving experiments after Ollama is stable.
- **llama.cpp direct:** benchmark/watch path only while tensor/split-mode remains experimental upstream.
- **TP=3 is validation, not an assumption:** the default helper uses `TENSOR_PARALLEL_SIZE=3`, but model architecture still decides whether it works.
- **Gemma4 FA gate:** before relying on Gemma4 in Ollama, test it on the RTX 3090s. If it crashes or produces bad output, set `OLLAMA_FLASH_ATTENTION=0` in the Ollama systemd override and retest.
- **Current version posture:** accept the current stable Ollama line (`v0.21.2` as of 2026-04-27) and avoid `0.21.3-rc*` for day one; the vLLM helper is now pinned to `v0.19.1`.

## Static IP Safety

Static IP is disabled by default.

Set `STATIC_IP_CIDR` and `STATIC_GATEWAY` before use. The script writes `/etc/netplan/99-nodehome-static.yaml` and runs `netplan generate`, but it does **not** automatically apply the netplan change. Apply it from local console when ready:

```bash
sudo netplan apply
```

## SSH Safety

Password SSH auth is disabled only if `ADMIN_USER` has at least one key in `authorized_keys`.

Set `SSH_PUBLIC_KEY` at the top of `bootstrap.sh` before running if this is a fresh SSH setup.

## vLLM

After bootstrap:

```bash
/opt/nodehome/vllm/launch_vllm.sh
```

Override defaults at runtime:

```bash
MODEL=Qwen/Qwen2.5-7B-Instruct TENSOR_PARALLEL_SIZE=3 PORT=8000 /opt/nodehome/vllm/launch_vllm.sh
```

CPU KV cache offload test:

```bash
CPU_OFFLOAD_GB=32 MODEL=<70B-model> TENSOR_PARALLEL_SIZE=3 /opt/nodehome/vllm/launch_vllm.sh
```

Use this to test whether 128GB system RAM can buy useful context/model headroom beyond the 72GB VRAM ceiling. Measure throughput against the no-offload run before treating it as a default.

Current helper image:

```bash
vllm/vllm-openai:v0.19.1
```

The repo wrapper is:

```bash
bash scripts/launch_vllm.sh
```

## Proxmox

Proxmox is intentionally not part of `bootstrap.sh`.

Run this only as a reminder:

```bash
bash scripts/proxmox-warning.sh
```

## Post-Run Checks

```bash
nvidia-smi
docker run --rm --gpus all nvidia/cuda:12.4.0-base-ubuntu24.04 nvidia-smi
ollama run qwen2:1.5b "hello"
```

Additional stack gates:

```bash
# Gemma4/Ollama FA gate
ollama run <gemma4-model-tag> "Say hello in one sentence."

# vLLM TP=3 validation
TENSOR_PARALLEL_SIZE=3 /opt/nodehome/vllm/launch_vllm.sh

# vLLM CPU KV offload validation
CPU_OFFLOAD_GB=32 TENSOR_PARALLEL_SIZE=3 /opt/nodehome/vllm/launch_vllm.sh
```

If the NVIDIA driver was newly installed, reboot before final GPU validation.
