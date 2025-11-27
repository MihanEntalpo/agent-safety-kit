#!/usr/bin/env bash
set -euo pipefail

if ! command -v apt-get >/dev/null 2>&1; then
  echo "Поддерживаются только deb-based системы с apt." >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
sudo apt-get update
sudo apt-get install -y snapd qemu-kvm libvirt-daemon-system libvirt-clients bridge-utils

if ! command -v snap >/dev/null 2>&1; then
  echo "snap недоступен после установки snapd. Проверьте установку и повторите попытку." >&2
  exit 1
fi

sudo snap install multipass --classic

echo "Multipass установлен."
