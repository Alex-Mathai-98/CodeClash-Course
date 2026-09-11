#!/usr/bin/env bash
set -euo pipefail

# --- Node.js 20 (for Claude Code) ---
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt-get install -y --no-install-recommends nodejs

# --- Claude Code ---
npm install -g @anthropic-ai/claude-code

# --- python -> python3 symlink ---
apt-get install -y --no-install-recommends python-is-python3

# --- jq (required by .claude/hooks/* to parse PreToolUse tool JSON) ---
apt-get install -y --no-install-recommends jq

# --- Git safe directory (host-owned .git mounted into container running as root) ---
# AIDEV-NOTE: honors a custom workdir passed by the Dockerfile (APP_DIR=@@WORKDIR@@); defaults to /app.
git config --global --add safe.directory "${APP_DIR:-/app}"

# --- Cleanup ---
rm -rf /var/lib/apt/lists/*
