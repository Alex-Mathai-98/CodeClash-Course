#!/usr/bin/env bash
set -euo pipefail

# init.sh — render the sysbox + Claude Code template into a target repo.
# Usage: init.sh <target-repo-dir> [conf-file] [--force]
#   <target-repo-dir>  where Dockerfile.sysbox + docker-compose.sysbox.yml + docker/ land
#   [conf-file]        token values (default: ./newproject.conf beside this script)
#   --force            overwrite existing files in the target
# AIDEV-NOTE: single error boundary = `set -euo pipefail` + the arg checks below.

TEMPLATE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

FORCE=0
POSarg=()
for a in "$@"; do
  if [[ "$a" == "--force" ]]; then FORCE=1; else POSarg+=("$a"); fi
done

TARGET="${POSarg[0]:-}"
CONF="${POSarg[1]:-$TEMPLATE_DIR/newproject.conf}"

[[ -n "$TARGET" ]] || { echo "usage: init.sh <target-repo-dir> [conf-file] [--force]" >&2; exit 2; }
[[ -d "$TARGET" ]]  || { echo "error: target dir not found: $TARGET" >&2; exit 2; }
[[ -f "$CONF" ]]    || { echo "error: conf not found: $CONF" >&2; exit 2; }

# Load token values into the environment.
# shellcheck disable=SC1090
source "$CONF"

TOKEN_NAMES=(BASE_IMAGE SYSTEM_PACKAGES WORKDIR DEP_INSTALL PROJECT_COPY ENV_VARS \
             SERVICE_NAME ENV_FILE VOLUMES COMPOSE_ENV WATCH)
export "${TOKEN_NAMES[@]}"

render() {   # render <template> <dest>
  local tmpl="$1" dest="$2"
  if [[ -e "$dest" && "$FORCE" -ne 1 ]]; then
    echo "error: $dest exists (use --force to overwrite)" >&2; exit 1
  fi
  # AIDEV-NOTE: python does multi-line-safe @@TOKEN@@ substitution; sed/eval can't.
  TOKEN_LIST="${TOKEN_NAMES[*]}" python3 - "$tmpl" "$dest" <<'PY'
import os, sys
tmpl, dest = sys.argv[1], sys.argv[2]
text = open(tmpl).read()
for key in os.environ["TOKEN_LIST"].split():
    text = text.replace(f"@@{key}@@", os.environ.get(key, ""))
open(dest, "w").write(text)
PY
  echo "  rendered $dest"
}

render "$TEMPLATE_DIR/Dockerfile.sysbox.tmpl"         "$TARGET/Dockerfile.sysbox"
render "$TEMPLATE_DIR/docker-compose.sysbox.yml.tmpl" "$TARGET/docker-compose.sysbox.yml"

# Copy the canonical generic scripts (single source of truth) into the target.
mkdir -p "$TARGET/docker"
cp -R "$TEMPLATE_DIR/docker/." "$TARGET/docker/"
echo "  copied generic docker/ scripts + assets"

cat <<EOF

Done. Next steps in $TARGET:
  1. Create ${ENV_FILE:-./dev.env} with any secrets / API keys.
  2. Set SERVICE_NAME + SYSTEM_PACKAGES in your conf, and adjust the DEP_INSTALL /
     PROJECT_COPY paths if your layout differs (unset tokens render as empty sections).
  3. Build + run:
       docker compose -f docker-compose.sysbox.yml up --build -d
       docker compose -f docker-compose.sysbox.yml exec ${SERVICE_NAME:-<service>} zsh
EOF
