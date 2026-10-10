#!/bin/bash
# Update (or first install) Agent-Orc on another machine, from this repository: builds the web
# app and a wheel here, ships it over SSH and installs it there, so that machine needs neither
# the source nor Node. The ssh arguments are passed on as they are:
#     deploy/deploy.sh -p 2222 mp@10.0.0.2
# A new machine then needs `ssh -t <it> agent-orc setup` once, and another deploy to start it.
set -euo pipefail

[ $# -ge 1 ] || { echo "Usage: $0 [ssh options] [user@]host" >&2; exit 2; }

REPO=$(cd "$(dirname "$0")/.." && pwd)
LOCAL_VENV=${XDG_DATA_HOME:-$HOME/.local/share}/agent-orc/venv

cd "$REPO"
if [ -n "$(git status --porcelain)" ]; then
    echo "Uncommitted changes in $REPO — commit them first; only committed code is shipped." >&2
    exit 1
fi

(cd frontend && npm ci && npm run build)
PAYLOAD=$(mktemp -d)
trap 'rm -rf "$PAYLOAD"' EXIT
"$LOCAL_VENV/bin/pip" wheel -q . --no-deps -w "$PAYLOAD"
cp deploy/agent-orc.user.service "$PAYLOAD/agent-orc.service"
cp deploy/remote-install.sh "$PAYLOAD/remote-install.sh"

# The files travel as one tar stream and are unpacked into a folder of their own, which goes
# again at the end.
tar -C "$PAYLOAD" -c . | ssh "$@" \
    'SHIPPED=$(mktemp -d) && trap "rm -rf $SHIPPED" EXIT && tar -x -C "$SHIPPED" && bash "$SHIPPED/remote-install.sh" "$SHIPPED"'
echo "Deployed $(git rev-parse --short HEAD) to $*."
