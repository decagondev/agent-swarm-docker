#!/usr/bin/env bash
# Tear down the demo. Removes the stack + named volume; leaves Swarm running
# (cheap to keep around). Pass --leave-swarm to also `docker swarm leave`.
set -euo pipefail

STACK="${AGENT_SWARM_STACK:-agent-swarm}"

echo "→ docker stack rm $STACK"
docker stack rm "$STACK" >/dev/null || true

# Wait for service AND task-container teardown so the volume can be removed cleanly.
# On Docker Desktop the task container can outlive its service by a few seconds,
# which would race with `docker volume rm` below.
echo "→ waiting for services and task containers to fully tear down"
for _ in {1..30}; do
  svcs="$(docker service ls --filter "label=com.docker.stack.namespace=${STACK}" -q | wc -l)"
  ctrs="$(docker ps -aq --filter "label=com.docker.stack.namespace=${STACK}" | wc -l)"
  if [[ "$svcs" -eq 0 && "$ctrs" -eq 0 ]]; then
    break
  fi
  sleep 1
done

echo "→ removing volume ${STACK}_shared-data (if present)"
if docker volume inspect "${STACK}_shared-data" >/dev/null 2>&1; then
  if ! docker volume rm "${STACK}_shared-data"; then
    echo "⚠️  volume ${STACK}_shared-data still in use; leaving in place" >&2
  fi
fi

if [[ "${1:-}" == "--leave-swarm" ]]; then
  echo "→ docker swarm leave --force"
  docker swarm leave --force >/dev/null
fi

echo "✅ Teardown complete."
