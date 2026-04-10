#!/usr/bin/env bash
set -euo pipefail

VLLM_SCRIPT="${VLLM_SCRIPT:-/opt/nodehome/vllm/launch_vllm.sh}"

if [[ ! -x "${VLLM_SCRIPT}" ]]; then
  echo "vLLM launch helper not found at ${VLLM_SCRIPT}." >&2
  echo "Run sudo bash scripts/bootstrap.sh first, or set VLLM_SCRIPT to the helper path." >&2
  exit 1
fi

exec "${VLLM_SCRIPT}" "$@"
