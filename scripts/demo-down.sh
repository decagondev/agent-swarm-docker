#!/usr/bin/env bash
# Tear down the demo. Removes the stack + named volume; leaves Swarm running
# (cheap to keep around). Pass --leave-swarm to also `docker swarm leave`.
set -euo pipefail

STACK="${AGENT_SWARM_STACK:-agent-swarm}"

echo "→ docker stack rm $STACK"
docker stack rm "$STACK" >/dev/null || true

# Wait for service teardown so the volume can be removed cleanly.
echo "→ waiting for services to fully tear down"
for _ in {1..30}; do
  remaining="$(docker service ls --filter "label=com.docker.stack.namespace=${STACK}" -q | wc -l)"
  if [[ "$remaining" -eq 0 ]]; then
    break
  fi
  sleep 1
done

echo "→ removing volume ${STACK}_shared-data (if present)"
docker volume rm "${STACK}_shared-data" 2>/dev/null || true

if [[ "${1:-}" == "--leave-swarm" ]]; then
  echo "→ docker swarm leave --force"
  docker swarm leave --force >/dev/null
fi

echo "✅ Teardown complete."
