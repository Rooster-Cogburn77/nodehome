#!/usr/bin/env bash
set -euo pipefail

cat <<'MSG'
Proxmox is intentionally out of scope for the day-one Ubuntu bootstrap.

Why:
- Proxmox changes the host/kernel model.
- Bare-metal NVIDIA drivers, Docker GPU access, Ollama, and vLLM should be validated first.
- If Proxmox is chosen later, treat it as a separate migration plan, not an add-on step.

Do not run Proxmox setup on top of this bootstrap without a separate host plan.
MSG
