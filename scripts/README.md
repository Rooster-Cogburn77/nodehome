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
MODEL=Qwen/Qwen2.5-7B-Instruct TENSOR_PARALLEL_SIZE=1 PORT=8000 /opt/nodehome/vllm/launch_vllm.sh
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

If the NVIDIA driver was newly installed, reboot before final GPU validation.
