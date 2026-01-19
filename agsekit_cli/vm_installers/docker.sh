#!/usr/bin/env bash
set -euo pipefail

if command -v docker >/dev/null 2>&1; then
  echo "Docker is already installed."
  exit 0
fi

echo "Installing Docker Engine via Docker apt repository..."
sudo apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

sudo tee /etc/apt/sources.list.d/docker.sources >/dev/null <<EOF_SOURCES
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
Components: stable
Signed-By: /etc/apt/keyrings/docker.asc
EOF_SOURCES

sudo apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
  docker-ce \
  docker-ce-cli \
  containerd.io \
  docker-buildx-plugin \
  docker-compose-plugin

if id -nG "$USER" | grep -qw docker; then
  echo "User $USER is already in the docker group."
else
  sudo usermod -aG docker "$USER" || true
fi

echo "Docker installation complete."
