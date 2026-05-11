#!/usr/bin/env bash
# Invoke the Supervisor inside the running stack container.
# Usage: ./scripts/demo-run.sh "Your prompt here."
set -euo pipefail

STACK="${AGENT_SWARM_STACK:-agent-swarm}"
SERVICE="${STACK}_supervisor"

if [[ $# -eq 0 ]]; then
  echo "Usage: $0 \"<prompt>\"" >&2
  exit 2
fi

# Find the running task container backing the supervisor service.
CONTAINER="$(docker ps \
  --filter "label=com.docker.swarm.service.name=${SERVICE}" \
  --format '{{.ID}}' | head -n1)"

if [[ -z "$CONTAINER" ]]; then
  echo "Error: no running container for service ${SERVICE}." >&2
  echo "Did you run ./scripts/demo-up.sh ?" >&2
  exit 1
fi

echo "→ exec into ${CONTAINER} (service ${SERVICE})"
exec docker exec -i "$CONTAINER" \
  python supervisor.py --executor swarm "$@"
