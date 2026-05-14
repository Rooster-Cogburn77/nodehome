# NVIDIA Power Cap Runbook

**Status:** Draft recipe. Not installed unless explicitly executed on `homelab`.
**Last Updated:** 2026-05-14

## Purpose

Apply the validated sustained 2-GPU vLLM operating profile after boot:

- GPU 0: `300 W`
- GPU 1: `300 W`
- GPU 2: untouched while the temporary pigtail rule is active

The `nvidia-smi -pl` setting is runtime state. It resets on reboot, so a systemd unit is needed if this profile should survive restarts.

Deployment status: installed and enabled on `homelab` on 2026-05-14. First live run exited `status=0/SUCCESS` and verified GPU0/GPU1 at `300.00 W`; boot-time execution will be verified on the next natural reboot.

## Manual Command

Use this when testing or after a reboot before the unit exists:

```bash
sudo nvidia-smi -i 0,1 -pl 300
nvidia-smi -i 0,1 --query-gpu=index,power.limit,power.draw,temperature.gpu,fan.speed --format=csv
```

Expected verification:

```text
0, 300.00 W, ...
1, 300.00 W, ...
```

Do not include GPU 2 in the command until the proper SF-1600F14HT PCIe cable is installed and the temporary pigtail rule is retired.

## Persistent Unit

Create `/etc/systemd/system/nvidia-power-cap.service`:

```ini
[Unit]
Description=Apply NVIDIA GPU power limits for 2-GPU vLLM profile

[Service]
Type=oneshot
ExecStart=/usr/bin/nvidia-smi -i 0,1 -pl 300
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
```

Enable and run:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now nvidia-power-cap.service
systemctl status nvidia-power-cap.service --no-pager
nvidia-smi -i 0,1 --query-gpu=index,power.limit --format=csv
```

## Rollback

```bash
sudo systemctl disable --now nvidia-power-cap.service
sudo rm /etc/systemd/system/nvidia-power-cap.service
sudo systemctl daemon-reload
sudo nvidia-smi -i 0,1 -pl 350
```

Rollback should restore GPUs 0 and 1 to the stock `350 W` limit. A reboot also clears runtime-only power limits, but it does not remove an enabled unit.

## Evidence

Validated on 2026-05-14 with `Qwen/Qwen2.5-32B-Instruct-AWQ` under vLLM TP=2:

| Config | Final GPU0 | Final GPU1 | GPU2 state | Request average |
|--------|------------|------------|------------|-----------------|
| `350 W`, no top fan | `83-84 C` / `90% fan` | `76-77 C` | `1 MiB`, idle | not measured |
| `350 W + top fan` | `77 C` / `82% fan` | `71 C` / `72% fan` | `1 MiB`, idle | `~4.96 s` |
| `300 W + top fan` | `76 C` / `78% fan` | `70 C` / `69% fan` | `1 MiB`, idle | `~5.16 s` |

Conclusion: `300 W + top fan` costs roughly 4% wall-clock latency on the measured request while reducing power draw and preserving materially better thermal/acoustic headroom than stock `350 W` operation.
