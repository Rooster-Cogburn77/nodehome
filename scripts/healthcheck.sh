#!/usr/bin/env bash
# Sovereign Node health check — single-command operational status.
#
# Run on the homelab server. Read-only: makes no changes. Reports:
#   * host kernel + uptime + load
#   * 3-GPU status (driver, temps, mem, util, PCIe link)
#   * NVMe storage (capacity, wear, smart status)
#   * Ollama systemd service + model count + LAN bind
#   * Docker container states (vllm-server, open-webui)
#   * API reachability (Ollama, vLLM, Open WebUI)
#   * BMC reachability (LAN, USB-NIC, channel info)
#   * Recent kernel errors (last 1 hour)
#
# Exit code: 0 if everything looks healthy, non-zero if any check failed.
# Usage:
#   ./scripts/healthcheck.sh           # human-readable
#   ./scripts/healthcheck.sh --quiet   # only print failures
#
# Authored 2026-05-10. Update as the stack evolves.

set -u

QUIET=0
[[ "${1:-}" == "--quiet" ]] && QUIET=1

# Colors only when stdout is a tty
if [[ -t 1 ]]; then
  GREEN=$'\033[0;32m'
  RED=$'\033[0;31m'
  YELLOW=$'\033[0;33m'
  BLUE=$'\033[0;34m'
  BOLD=$'\033[1m'
  RESET=$'\033[0m'
else
  GREEN=""; RED=""; YELLOW=""; BLUE=""; BOLD=""; RESET=""
fi

FAIL_COUNT=0
WARN_COUNT=0

section() {
  [[ $QUIET -eq 1 ]] && return
  printf '\n%s%s== %s ==%s\n' "$BOLD" "$BLUE" "$1" "$RESET"
}

ok() {
  [[ $QUIET -eq 1 ]] && return
  printf '  %s[OK]%s %s\n' "$GREEN" "$RESET" "$1"
}

warn() {
  WARN_COUNT=$((WARN_COUNT + 1))
  printf '  %s[WARN]%s %s\n' "$YELLOW" "$RESET" "$1"
}

fail() {
  FAIL_COUNT=$((FAIL_COUNT + 1))
  printf '  %s[FAIL]%s %s\n' "$RED" "$RESET" "$1"
}

info() {
  [[ $QUIET -eq 1 ]] && return
  printf '         %s\n' "$1"
}

# ---------- host ----------

section "Host"
HOSTNAME_VAL=$(hostname)
KERNEL_VAL=$(uname -r)
UPTIME_VAL=$(uptime -p 2>/dev/null || uptime)
LOAD_VAL=$(awk '{print $1, $2, $3}' /proc/loadavg)
ok "hostname: $HOSTNAME_VAL"
info "kernel: $KERNEL_VAL"
info "uptime: $UPTIME_VAL"
info "loadavg (1/5/15): $LOAD_VAL"

# ---------- GPUs ----------

section "GPUs"
if ! command -v nvidia-smi >/dev/null 2>&1; then
  fail "nvidia-smi not found"
else
  GPU_COUNT=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | wc -l)
  if [[ $GPU_COUNT -eq 0 ]]; then
    fail "nvidia-smi returns no GPUs"
  else
    ok "$GPU_COUNT GPU(s) detected"
    while IFS=, read -r idx name temp mem_used mem_total util pwr_draw pwr_cap link_gen link_width; do
      idx=$(echo "$idx" | xargs)
      name=$(echo "$name" | xargs)
      info "GPU $idx: $name | ${temp}C | ${mem_used}/${mem_total} MiB | util ${util}% | ${pwr_draw}/${pwr_cap} W | PCIe gen ${link_gen} x${link_width}"
    done < <(nvidia-smi --query-gpu=index,name,temperature.gpu,memory.used,memory.total,utilization.gpu,power.draw,power.limit,pcie.link.gen.current,pcie.link.width.current --format=csv,noheader,nounits)
  fi
fi

# ---------- NVMe ----------

section "Storage"
ROOT_USE=$(df -h / | awk 'NR==2 {print $5}' | tr -d '%')
ROOT_AVAIL=$(df -h / | awk 'NR==2 {print $4}')
if [[ $ROOT_USE -ge 90 ]]; then
  fail "/ is ${ROOT_USE}% full (avail $ROOT_AVAIL)"
elif [[ $ROOT_USE -ge 75 ]]; then
  warn "/ is ${ROOT_USE}% full (avail $ROOT_AVAIL)"
else
  ok "/ is ${ROOT_USE}% full (avail $ROOT_AVAIL)"
fi

if command -v smartctl >/dev/null 2>&1 && [[ -e /dev/nvme0n1 ]]; then
  if SMART_OUT=$(sudo -n smartctl -A /dev/nvme0n1 2>/dev/null); then
    PCT_USED=$(echo "$SMART_OUT" | awk -F: '/Percentage Used/ {gsub(/[^0-9]/,"",$2); print $2; exit}')
    SPARE=$(echo "$SMART_OUT" | awk -F: '/Available Spare:/ {gsub(/[^0-9]/,"",$2); print $2; exit}')
    UNSAFE=$(echo "$SMART_OUT" | awk -F: '/Unsafe Shutdowns/ {gsub(/[^0-9]/,"",$2); print $2; exit}')
    if [[ -n $PCT_USED && $PCT_USED -ge 80 ]]; then
      warn "NVMe wear: ${PCT_USED}%"
    else
      ok "NVMe wear: ${PCT_USED:-?}%"
    fi
    info "available spare: ${SPARE:-?}%, unsafe shutdowns: ${UNSAFE:-?}"
  else
    info "smartctl needs sudo without password; skipping detailed NVMe stats"
  fi
else
  info "smartctl not installed or no /dev/nvme0n1; skipping NVMe stats"
fi

# ---------- Ollama ----------

section "Ollama"
if systemctl is-active --quiet ollama 2>/dev/null; then
  ok "ollama.service active"
  OLLAMA_LISTEN=$(ss -tlnp 2>/dev/null | awk '/:11434 / {print $4; exit}')
  if [[ -z $OLLAMA_LISTEN ]]; then
    fail "no listener on port 11434"
  else
    info "listening on $OLLAMA_LISTEN"
  fi
  if MODEL_LIST=$(curl -s --max-time 5 http://localhost:11434/api/tags); then
    MODEL_COUNT=$(echo "$MODEL_LIST" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('models',[])))" 2>/dev/null || echo 0)
    if [[ $MODEL_COUNT -gt 0 ]]; then
      ok "Ollama API: $MODEL_COUNT model(s) available"
    else
      warn "Ollama API up but no models registered"
    fi
  else
    fail "Ollama API on :11434 not responding"
  fi
else
  fail "ollama.service not active"
fi

# ---------- Docker containers ----------

section "Docker containers"
if ! command -v docker >/dev/null 2>&1; then
  fail "docker not installed"
else
  for cname in vllm-server open-webui; do
    STATE=$(sudo -n docker inspect --format '{{.State.Status}}' "$cname" 2>/dev/null || echo "missing")
    case "$STATE" in
      running) ok "$cname: running" ;;
      missing) warn "$cname: container not present" ;;
      *)       fail "$cname: state=$STATE" ;;
    esac
  done
fi

# ---------- API reachability ----------

section "Service APIs"
# vLLM
if VLLM_RESP=$(curl -s --max-time 5 http://localhost:8000/v1/models); then
  if echo "$VLLM_RESP" | grep -q '"data"'; then
    VLLM_MODEL=$(echo "$VLLM_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('data',[{}])[0].get('id','?'))" 2>/dev/null || echo "?")
    ok "vLLM /v1/models 200, model=$VLLM_MODEL"
  else
    warn "vLLM responded but body unexpected"
  fi
else
  warn "vLLM /v1/models not reachable (container may be mid-load; cold load is ~90 sec)"
fi
# Open WebUI
WEBUI_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 http://localhost:3000 || echo "000")
case "$WEBUI_CODE" in
  200|301|302) ok "Open WebUI HTTP $WEBUI_CODE" ;;
  000)         fail "Open WebUI: no response" ;;
  *)           warn "Open WebUI: HTTP $WEBUI_CODE" ;;
esac

# ---------- BMC ----------

section "BMC / IPMI"
if command -v ipmitool >/dev/null 2>&1; then
  if BMC_LAN=$(sudo -n ipmitool lan print 1 2>/dev/null); then
    BMC_IP=$(echo "$BMC_LAN" | awk -F: '/^IP Address[ ]+:/ {gsub(/ /,"",$2); print $2; exit}')
    BMC_SRC=$(echo "$BMC_LAN" | awk -F: '/IP Address Source/ {sub(/^[ \t]+/,"",$2); print $2; exit}')
    BMC_MAC=$(echo "$BMC_LAN" | awk -F: '/^MAC Address[ ]+:/ {sub(/^[ \t]+/,"",$2); print $2; exit}')
    if [[ "$BMC_IP" == "0.0.0.0" || -z "$BMC_IP" ]]; then
      warn "BMC LAN port not patched (IP=$BMC_IP, source=$BMC_SRC)"
    else
      ok "BMC reachable: $BMC_IP ($BMC_SRC)"
    fi
    info "BMC NIC MAC: $BMC_MAC"
  else
    info "ipmitool needs sudo without password to query LAN; skipping"
  fi
  if ip -brief a 2>/dev/null | grep -q "169.254.3"; then
    info "BMC USB virtual NIC link-local 169.254.3.x present (in-band path OK)"
  fi
else
  info "ipmitool not installed; skipping BMC checks"
fi

# ---------- Kernel errors ----------

section "Recent kernel errors (last 1 hour)"
if ERR_OUT=$(sudo -n journalctl -k --since "1 hour ago" -p err --no-pager 2>/dev/null); then
  if [[ -z "$ERR_OUT" || "$ERR_OUT" == *"No entries"* ]]; then
    ok "no kernel error-level entries in the last hour"
  else
    ERR_COUNT=$(echo "$ERR_OUT" | grep -c "^")
    warn "$ERR_COUNT kernel error-level lines in the last hour"
    [[ $QUIET -eq 0 ]] && echo "$ERR_OUT" | tail -10 | sed 's/^/         /'
  fi
else
  info "journalctl needs sudo without password; skipping kernel error scan"
fi

# ---------- summary ----------

section "Summary"
if [[ $FAIL_COUNT -eq 0 && $WARN_COUNT -eq 0 ]]; then
  printf '%s%s[HEALTHY]%s no failures, no warnings\n' "$BOLD" "$GREEN" "$RESET"
  exit 0
elif [[ $FAIL_COUNT -eq 0 ]]; then
  printf '%s%s[HEALTHY]%s %d warning(s), no failures\n' "$BOLD" "$YELLOW" "$RESET" "$WARN_COUNT"
  exit 0
else
  printf '%s%s[UNHEALTHY]%s %d failure(s), %d warning(s)\n' "$BOLD" "$RED" "$RESET" "$FAIL_COUNT" "$WARN_COUNT"
  exit 1
fi
