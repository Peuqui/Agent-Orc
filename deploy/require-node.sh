#!/bin/bash
# Run before the web app is built: Vite needs Node.js 20.19+ or 22.12+, and an older one fails deep
# inside the build with an error that does not say so (Ubuntu 24.04's own package is Node 18).
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
