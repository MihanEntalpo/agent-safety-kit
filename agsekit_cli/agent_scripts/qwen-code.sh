#!/usr/bin/env bash
set -euo pipefail

echo "Installing Qwen Code agent..."

curl -qL https://www.npmjs.com/install.sh | sudo bash
npm install -g @qwen-code/qwen-code@latest
