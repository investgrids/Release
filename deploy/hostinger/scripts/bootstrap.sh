#!/usr/bin/env bash
# One-time setup of a fresh Ubuntu 24.04 VPS: firewall, key-only SSH, swap, fail2ban, automatic security updates, Docker.
# Safe order (cannot lock you out): SSH allowed in the firewall BEFORE it is enabled; sshd config validated BEFORE reload; sshd is reloaded, never restarted.
# Run as root on the server:  bash bootstrap.sh      Requires that your SSH public key is already in /root/.ssh/authorized_keys.
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
grep -q 'ssh-' /root/.ssh/authorized_keys || { echo "no SSH key in /root/.ssh/authorized_keys: refusing to disable passwords"; exit 2; }

echo "== firewall"
ufw allow 22/tcp comment ssh >/dev/null; ufw allow 80/tcp comment http >/dev/null; ufw allow 443/tcp comment https >/dev/null
ufw default deny incoming >/dev/null; ufw default allow outgoing >/dev/null; ufw --force enable >/dev/null; ufw status | head -3

echo "== ssh key-only (00- drop-in is read first and wins)"
cat > /etc/ssh/sshd_config.d/00-hardening.conf <<'EOF'
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin prohibit-password
MaxAuthTries 3
LoginGraceTime 30
EOF
sshd -t && systemctl reload ssh

echo "== swap 2 GB, swappiness 10"
if ! swapon --show | grep -q swapfile; then
  fallocate -l 2G /swapfile; chmod 600 /swapfile; mkswap /swapfile >/dev/null; swapon /swapfile
  grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi
echo 'vm.swappiness=10' > /etc/sysctl.d/99-swappiness.conf; sysctl -p /etc/sysctl.d/99-swappiness.conf >/dev/null

echo "== fail2ban + unattended upgrades"
apt-get update -qq; apt-get install -y -qq fail2ban unattended-upgrades ca-certificates curl gnupg git >/dev/null
printf '[sshd]\nenabled = true\nmaxretry = 4\nfindtime = 10m\nbantime = 1h\n' > /etc/fail2ban/jail.d/sshd.local
systemctl enable --now fail2ban >/dev/null 2>&1; systemctl restart fail2ban

echo "== docker engine + compose (skipped if already installed)"
if ! command -v docker >/dev/null; then
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc; chmod a+r /etc/apt/keyrings/docker.asc
  . /etc/os-release
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" > /etc/apt/sources.list.d/docker.list
  apt-get update -qq; apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin >/dev/null
fi
printf '{ "log-driver": "json-file", "log-opts": { "max-size": "10m", "max-file": "3" } }\n' > /etc/docker/daemon.json
systemctl enable --now docker >/dev/null 2>&1; systemctl restart docker
docker --version; docker compose version

mkdir -p /opt/marketripple/backups
echo "BOOTSTRAP DONE. Next: clone the repo to /opt/marketripple/src, create /opt/marketripple/.env (mode 600), then scripts/deploy.sh <sha>."
