#!/bin/bash
# Install (or update) Agent-Orc for the current user from this repository: builds the web app,
# installs the package non-editable into its own venv and links the command into ~/.local/bin.
# The service runs this copy, so a restart never picks up half-written code from the work tree.
set -euo pipefail

REPO=$(cd "$(dirname "$0")/.." && pwd)
VENV=${XDG_DATA_HOME:-$HOME/.local/share}/agent-orc/venv
BIN=$HOME/.local/bin

cd "$REPO"
if [ -n "$(git status --porcelain)" ]; then
    echo "Uncommitted changes in $REPO — commit them first; only committed code is installed." >&2
    exit 1
fi

"$REPO/deploy/preflight.sh"
(cd frontend && npm ci && npm run build)
[ -d "$VENV" ] || python3 -m venv "$VENV"
"$VENV/bin/pip" install .
mkdir -p "$BIN"
ln -sfn "$VENV/bin/agent-orc" "$BIN/agent-orc"
echo "Installed $(git rev-parse --short HEAD) to $VENV."

# A running service would otherwise keep the old code while already serving the new web app.
# Agents keep running (KillMode=process); the user needs the right to restart the unit (polkit).
UNIT="agent-orc@$(id -un).service"
if systemctl is-active --quiet "$UNIT"; then
    systemctl restart "$UNIT"
    echo "Restarted $UNIT."
fi
