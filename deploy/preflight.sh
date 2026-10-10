#!/bin/bash
# Run before anything is built or installed: the tools Agent-Orc needs, with versions, so a machine
# that lacks them is told so plainly instead of failing deep inside the build. Vite needs Node.js
# 20.19+ or 22.12+ (Ubuntu 24.04's own package is Node 18), Agent-Orc itself Python 3.12+.
set -euo pipefail

if ! command -v node >/dev/null; then
    echo "Node.js is missing; building the web app needs 20.19+ or 22.12+ (see the README)." >&2
    exit 1
fi
if ! node -e 'const [major, minor] = process.versions.node.split(".").map(Number);
    process.exit((major === 20 && minor >= 19) || (major === 22 && minor >= 12) || major > 22 ? 0 : 1)'; then
    echo "Node.js $(node --version) is too old to build the web app: it needs 20.19+ or 22.12+ (see the README)." >&2
    exit 1
fi
if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)' 2>/dev/null; then
    echo "Python 3.12 or newer is needed; python3 here is $(python3 --version 2>&1) (see the README)." >&2
    exit 1
fi
