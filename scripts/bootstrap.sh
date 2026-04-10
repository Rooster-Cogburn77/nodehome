#!/usr/bin/env bash
set -euo pipefail

###############################################################################
# Nodehome / Sovereign Node Day-One Bootstrap
# Target: Ubuntu 24.04 LTS bare metal only.
#
# Edit tunables in this block before running.
###############################################################################

HOSTNAME="nodehome"
ADMIN_USER="${SUDO_USER:-$USER}"

# Static IP is disabled until STATIC_IP_CIDR is set.
# Example:
#   STATIC_IP_CIDR="192.168.1.50/24"
#   STATIC_GATEWAY="192.168.1.1"
#   STATIC_DNS="1.1.1.1,8.8.8.8"
# Leave NETPLAN_INTERFACE empty to auto-detect the default route interface.
STATIC_IP_CIDR=""
STATIC_GATEWAY=""
STATIC_DNS="1.1.1.1,8.8.8.8"
NETPLAN_INTERFACE=""

# SSH hardening:
# - If SSH_PUBLIC_KEY is set, it will be added to ADMIN_USER authorized_keys.
# - Password auth is disabled only if a key is present for ADMIN_USER.
SSH_PUBLIC_KEY=""
DISABLE_PASSWORD_AUTH_AFTER_KEY="true"

# NVIDIA / CUDA:
# - Set NVIDIA_DRIVER_PACKAGE to "auto" to use ubuntu-drivers autoinstall.
# - Or pin it, for example: "nvidia-driver-550".
NVIDIA_DRIVER_PACKAGE="auto"
CUDA_KEYRING_DEB_URL="https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2404/x86_64/cuda-keyring_1.1-1_all.deb"
CUDA_TOOLKIT_PACKAGE="cuda-toolkit-12-4"

# Ollama:
OLLAMA_HOST_BIND="0.0.0.0:11434"
OLLAMA_TEST_MODEL="qwen2:1.5b"
INSTALL_OLLAMA_TEST_MODEL="true"

# vLLM helper script defaults:
VLLM_DIR="/opt/nodehome/vllm"
VLLM_IMAGE="vllm/vllm-openai:latest"
VLLM_MODEL="Qwen/Qwen2.5-1.5B-Instruct"
VLLM_TENSOR_PARALLEL_SIZE="1"
VLLM_PORT="8000"

###############################################################################

log() {
  printf '\n==> %s\n' "$*"
}

warn() {
  printf '\nWARN: %s\n' "$*" >&2
}

need_root() {
  if [[ "${EUID}" -ne 0 ]]; then
    echo "Run with sudo: sudo bash scripts/bootstrap.sh" >&2
    exit 1
  fi
}

require_ubuntu_2404() {
  . /etc/os-release
  if [[ "${ID}" != "ubuntu" || "${VERSION_ID}" != "24.04" ]]; then
    echo "This bootstrap supports Ubuntu 24.04 LTS only. Found: ${PRETTY_NAME}" >&2
    exit 1
  fi
}

apt_install() {
  DEBIAN_FRONTEND=noninteractive apt-get install -y "$@"
}

default_interface() {
  if [[ -n "${NETPLAN_INTERFACE}" ]]; then
    echo "${NETPLAN_INTERFACE}"
    return
  fi
  ip route show default | awk '{print $5; exit}'
}

configure_static_ip() {
  if [[ -z "${STATIC_IP_CIDR}" ]]; then
    log "Static IP not configured; skipping netplan change."
    return
  fi
  if [[ -z "${STATIC_GATEWAY}" ]]; then
    echo "STATIC_GATEWAY must be set when STATIC_IP_CIDR is set." >&2
    exit 1
  fi

  local iface
  iface="$(default_interface)"
  if [[ -z "${iface}" ]]; then
    echo "Could not detect network interface. Set NETPLAN_INTERFACE at top of script." >&2
    exit 1
  fi

  log "Configuring static IP ${STATIC_IP_CIDR} on ${iface}."
  cat > /etc/netplan/99-nodehome-static.yaml <<EOF
network:
  version: 2
  ethernets:
    ${iface}:
      dhcp4: false
      addresses:
        - ${STATIC_IP_CIDR}
      routes:
        - to: default
          via: ${STATIC_GATEWAY}
      nameservers:
        addresses: [${STATIC_DNS}]
EOF
  netplan generate
  warn "Netplan file written. Apply manually from console when ready: sudo netplan apply"
}

configure_hostname() {
  log "Setting hostname to ${HOSTNAME}."
  hostnamectl set-hostname "${HOSTNAME}"
  if grep -qE '^127\.0\.1\.1\s+' /etc/hosts; then
    sed -i "s/^127\.0\.1\.1\s\+.*/127.0.1.1 ${HOSTNAME}/" /etc/hosts
  else
    printf '127.0.1.1 %s\n' "${HOSTNAME}" >> /etc/hosts
  fi
}

install_base_packages() {
  log "Updating base system and installing essentials."
  apt-get update
  DEBIAN_FRONTEND=noninteractive apt-get upgrade -y
  apt_install \
    apt-transport-https \
    build-essential \
    ca-certificates \
    curl \
    git \
    gnupg \
    htop \
    jq \
    lm-sensors \
    lsb-release \
    net-tools \
    nvtop \
    pciutils \
    python3 \
    python3-venv \
    software-properties-common \
    tmux \
    unzip \
    wget
}

configure_ssh() {
  log "Configuring SSH hardening."
  local home_dir auth_file
  home_dir="$(getent passwd "${ADMIN_USER}" | cut -d: -f6)"
  if [[ -z "${home_dir}" || ! -d "${home_dir}" ]]; then
    echo "Could not find home directory for ADMIN_USER=${ADMIN_USER}" >&2
    exit 1
  fi

  install -d -m 700 -o "${ADMIN_USER}" -g "${ADMIN_USER}" "${home_dir}/.ssh"
  auth_file="${home_dir}/.ssh/authorized_keys"
  touch "${auth_file}"
  chown "${ADMIN_USER}:${ADMIN_USER}" "${auth_file}"
  chmod 600 "${auth_file}"

  if [[ -n "${SSH_PUBLIC_KEY}" ]] && ! grep -qxF "${SSH_PUBLIC_KEY}" "${auth_file}"; then
    printf '%s\n' "${SSH_PUBLIC_KEY}" >> "${auth_file}"
  fi

  install -d /etc/ssh/sshd_config.d
  cat > /etc/ssh/sshd_config.d/99-nodehome-hardening.conf <<EOF
PermitRootLogin no
PubkeyAuthentication yes
KbdInteractiveAuthentication no
X11Forwarding no
EOF

  if [[ "${DISABLE_PASSWORD_AUTH_AFTER_KEY}" == "true" && -s "${auth_file}" ]]; then
    printf 'PasswordAuthentication no\n' >> /etc/ssh/sshd_config.d/99-nodehome-hardening.conf
    log "Password SSH auth disabled because ${auth_file} has at least one key."
  else
    warn "Password SSH auth left enabled. Add SSH_PUBLIC_KEY and rerun to disable it safely."
  fi

  systemctl reload ssh || systemctl reload sshd
}

install_nvidia_driver_cuda() {
  log "Installing NVIDIA driver and CUDA toolkit."
  apt_install ubuntu-drivers-common
  if [[ "${NVIDIA_DRIVER_PACKAGE}" == "auto" ]]; then
    ubuntu-drivers autoinstall
  else
    apt_install "${NVIDIA_DRIVER_PACKAGE}"
  fi

  local keyring_deb
  keyring_deb="/tmp/cuda-keyring.deb"
  wget -qO "${keyring_deb}" "${CUDA_KEYRING_DEB_URL}"
  dpkg -i "${keyring_deb}" || apt-get -f install -y
  apt-get update
  apt_install "${CUDA_TOOLKIT_PACKAGE}"

  if command -v nvidia-smi >/dev/null 2>&1; then
    nvidia-smi || warn "nvidia-smi failed. A reboot may be required before the driver is active."
  else
    warn "nvidia-smi not found after driver install. Reboot and re-check."
  fi
}

install_docker_nvidia_toolkit() {
  log "Installing Docker CE."
  install -m 0755 -d /etc/apt/keyrings
  if [[ ! -f /etc/apt/keyrings/docker.asc ]]; then
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
    chmod a+r /etc/apt/keyrings/docker.asc
  fi
  cat > /etc/apt/sources.list.d/docker.list <<EOF
deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "${VERSION_CODENAME}") stable
EOF
  apt-get update
  apt_install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  usermod -aG docker "${ADMIN_USER}"
  systemctl enable --now docker

  log "Installing NVIDIA Container Toolkit."
  curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
    | gpg --dearmor --yes -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
  curl -fsSL https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
    | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
    > /etc/apt/sources.list.d/nvidia-container-toolkit.list
  apt-get update
  apt_install nvidia-container-toolkit
  nvidia-ctk runtime configure --runtime=docker
  systemctl restart docker

  docker run --rm --gpus all nvidia/cuda:12.4.0-base-ubuntu24.04 nvidia-smi \
    || warn "Docker GPU smoke test failed. Reboot may be required."
}

install_ollama() {
  log "Installing and configuring Ollama."
  curl -fsSL https://ollama.com/install.sh | sh
  install -d /etc/systemd/system/ollama.service.d
  cat > /etc/systemd/system/ollama.service.d/override.conf <<EOF
[Service]
Environment="OLLAMA_HOST=${OLLAMA_HOST_BIND}"
EOF
  systemctl daemon-reload
  systemctl enable --now ollama
  systemctl restart ollama

  if [[ "${INSTALL_OLLAMA_TEST_MODEL}" == "true" ]]; then
    log "Pulling Ollama test model ${OLLAMA_TEST_MODEL}."
    sudo -H -u "${ADMIN_USER}" ollama pull "${OLLAMA_TEST_MODEL}" || warn "Ollama model pull failed."
    sudo -H -u "${ADMIN_USER}" ollama run "${OLLAMA_TEST_MODEL}" "hello" || warn "Ollama test inference failed."
  fi
}

write_vllm_launch_script() {
  log "Writing vLLM launch helper to ${VLLM_DIR}/launch_vllm.sh."
  install -d -m 0755 "${VLLM_DIR}"
  cat > "${VLLM_DIR}/launch_vllm.sh" <<EOF
#!/usr/bin/env bash
set -euo pipefail

VLLM_IMAGE="\${VLLM_IMAGE:-${VLLM_IMAGE}}"
MODEL="\${MODEL:-${VLLM_MODEL}}"
TENSOR_PARALLEL_SIZE="\${TENSOR_PARALLEL_SIZE:-${VLLM_TENSOR_PARALLEL_SIZE}}"
PORT="\${PORT:-${VLLM_PORT}}"
HF_HOME="\${HF_HOME:-\$HOME/.cache/huggingface}"

mkdir -p "\${HF_HOME}"

docker run --rm -it \\
  --gpus all \\
  --ipc=host \\
  -p "\${PORT}:8000" \\
  -v "\${HF_HOME}:/root/.cache/huggingface" \\
  "\${VLLM_IMAGE}" \\
  --host 0.0.0.0 \\
  --model "\${MODEL}" \\
  --tensor-parallel-size "\${TENSOR_PARALLEL_SIZE}"
EOF
  chmod 0755 "${VLLM_DIR}/launch_vllm.sh"
  chown -R "${ADMIN_USER}:${ADMIN_USER}" "${VLLM_DIR}"
}

write_proxmox_warning() {
  log "Writing Proxmox warning stub."
  install -d -m 0755 /opt/nodehome
  cat > /opt/nodehome/proxmox-warning.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
cat <<'MSG'
Proxmox is intentionally not installed by the day-one Ubuntu bootstrap.

Reason:
- Proxmox changes the host/kernel model.
- Bare-metal NVIDIA drivers, Docker GPU access, Ollama, and vLLM should be validated first.
- If Proxmox is chosen later, treat it as a separate migration plan, not an add-on step.
MSG
EOF
  chmod 0755 /opt/nodehome/proxmox-warning.sh
}

main() {
  need_root
  require_ubuntu_2404
  configure_hostname
  install_base_packages
  configure_static_ip
  configure_ssh
  install_nvidia_driver_cuda
  install_docker_nvidia_toolkit
  install_ollama
  write_vllm_launch_script
  write_proxmox_warning

  log "Bootstrap complete."
  warn "Reboot before final GPU validation if the NVIDIA driver was newly installed."
  cat <<EOF

Post-run checks:
  nvidia-smi
  docker run --rm --gpus all nvidia/cuda:12.4.0-base-ubuntu24.04 nvidia-smi
  ollama run ${OLLAMA_TEST_MODEL} "hello"
  ${VLLM_DIR}/launch_vllm.sh

If Docker group membership was just added, log out and back in before running docker as ${ADMIN_USER}.
EOF
}

main "$@"
