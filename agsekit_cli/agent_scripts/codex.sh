#!/usr/bin/env bash
set -euo pipefail

echo "Installing Codex agent..."

sudo apt-get update -y
sudo apt-get install -y nodejs npm

npm install -g @openai/codex
