#!/bin/bash
# Install (or update) Agent-Orc for the current user from this repository: builds the web app,
# installs the package non-editable into its own venv and links the command into ~/.local/bin.
# The service runs this copy, so a restart never picks up half-written code from the work tree.
set -euo pipefail

REPO=$(cd "$(dirname "$0")/.." && pwd)
VENV=${XDG_DATA_HOME:-$HOME/.local/share}/agent-orc/venv
BIN=$HOME/.local/bin

cd "$REPO"
# A clone installs only committed code; a downloaded ZIP has no git history and is taken as it is.
if [ -e .git ]; then
    if [ -n "$(git status --porcelain)" ]; then
        echo "Uncommitted changes in $REPO — commit them first; only committed code is installed." >&2
        exit 1
    fi
    VERSION=$(git rev-parse --short HEAD)
else
    VERSION="from an archive"
fi

"$REPO/deploy/preflight.sh"
(cd frontend && npm ci && npm run build)
# A venv without pip is the remains of a failed creation: made anew. Debian and Ubuntu ship Python
# without what venv needs for pip (`import venv` works, creating one does not).
if [ ! -x "$VENV/bin/pip" ] && ! python3 -m venv --clear "$VENV"; then
    echo "Could not create $VENV: install the venv package of python3 first (Debian/Ubuntu: sudo apt install python3-venv), then run this again." >&2
    exit 1
fi
"$VENV/bin/pip" install .
mkdir -p "$BIN"
ln -sfn "$VENV/bin/agent-orc" "$BIN/agent-orc"
echo "Installed $VERSION to $VENV."

# A running service would otherwise keep the old code while already serving the new web app.
# Agents keep running (KillMode=process); the user needs the right to restart the unit (polkit).
UNIT="agent-orc@$(id -un).service"
if systemctl is-active --quiet "$UNIT"; then
    # A config the new version no longer reads would stop the service at the restart.
    if ! "$VENV/bin/agent-orc" check-config; then
        echo "Not restarted: bring the config in line with the new version, then run this again." >&2
        exit 1
    fi
    systemctl restart "$UNIT"
    echo "Restarted $UNIT."
fi
