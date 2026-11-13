#!/usr/bin/env bash
set -euo pipefail

# --- Node.js 24 (for Claude Code) ---
# AIDEV-NOTE: Node 20 is EOL and unpatched for CVE-2026-111497 (bundled Brotli); use >= 24.22.1.
curl -fsSL https://deb.nodesource.com/setup_24.x | bash -
apt-get install -y --no-install-recommends nodejs

# --- OS security updates (base image ships stale packages, e.g. libbrotli1) ---
# AIDEV-NOTE: the nestybox base image lags Ubuntu security fixes; upgrade on every build.
apt-get upgrade -y --no-install-recommends

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
