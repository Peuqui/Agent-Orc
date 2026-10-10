#!/bin/bash
# Runs on the machine `deploy.sh` updates, from the folder it shipped (given as $1): installs the
# wheel into Agent-Orc's own venv, links the command and keeps the user service up to date.
set -euo pipefail

SHIPPED=$1
VENV=${XDG_DATA_HOME:-$HOME/.local/share}/agent-orc/venv
UNIT_DIR=${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user
CONFIG=${XDG_CONFIG_HOME:-$HOME/.config}/agent-orc/config.yaml
WHEEL=$(ls "$SHIPPED"/*.whl)

if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)' 2>/dev/null; then
    echo "Python 3.12 or newer is needed on this machine; python3 here is $(python3 --version 2>&1)." >&2
    exit 1
fi
[ -d "$VENV" ] || python3 -m venv "$VENV"
# The dependencies first; the wheel's version number stays the same between builds, so it is then
# put in again explicitly.
"$VENV/bin/pip" install -q "$WHEEL"
"$VENV/bin/pip" install -q --force-reinstall --no-deps "$WHEEL"
mkdir -p "$HOME/.local/bin"
ln -sfn "$VENV/bin/agent-orc" "$HOME/.local/bin/agent-orc"
echo "Installed $(basename "$WHEEL") to $VENV."

mkdir -p "$UNIT_DIR"
if ! cmp -s "$SHIPPED/agent-orc.service" "$UNIT_DIR/agent-orc.service"; then
    cp "$SHIPPED/agent-orc.service" "$UNIT_DIR/agent-orc.service"
    systemctl --user daemon-reload
    echo "Installed the user service."
fi

if [ ! -f "$CONFIG" ]; then
    echo "No config yet: run 'agent-orc setup' here (ssh -t), then deploy again to start the service."
    exit 0
fi
# Agents keep running (KillMode=process); enable also starts it when it is not running yet.
systemctl --user enable -q agent-orc.service
systemctl --user restart agent-orc.service
echo "Restarted agent-orc.service."
