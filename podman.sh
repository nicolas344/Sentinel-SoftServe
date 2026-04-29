#!/usr/bin/env bash
# Run podman-compose with the correct Podman socket wired in.
# Usage:  ./podman.sh up -d
#         ./podman.sh down
#         ./podman.sh logs -f backend
set -euo pipefail

# Ensure Podman machine is running
if ! podman machine inspect podman-machine-default --format '{{.State}}' 2>/dev/null | grep -q running; then
    echo "Starting Podman machine..."
    podman machine start
fi

# Point DOCKER_HOST at the macOS-side socket so host tooling (e.g. podman-compose) can reach the daemon
SOCKET_PATH="$(podman machine inspect podman-machine-default --format '{{.ConnectionInfo.PodmanSocket.Path}}' 2>/dev/null)"
export DOCKER_HOST="unix://${SOCKET_PATH}"

# Load Podman-specific env vars (DOCKER_SOCKET, etc.) into the environment
set -a
# shellcheck source=.env.podman
source "$(dirname "$0")/.env.podman"
set +a

exec podman-compose "$@"
