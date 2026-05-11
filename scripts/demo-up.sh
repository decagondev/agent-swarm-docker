#!/usr/bin/env bash
# Bring up the demo: swarm init (idempotent), build (skipped if cached), deploy.
# Run from repo root: ./scripts/demo-up.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

IMAGE="${AGENT_SWARM_IMAGE:-agent-swarm:latest}"
STACK="${AGENT_SWARM_STACK:-agent-swarm}"

# 1. Ensure swarm is initialised. Idempotent.
if [[ "$(docker info --format '{{.Swarm.LocalNodeState}}' 2>/dev/null)" != "active" ]]; then
  echo "→ docker swarm init"
  docker swarm init >/dev/null
else
  echo "→ swarm already active"
fi

# 2. Build the image. Skip if it already exists locally — keeps the live demo snappy.
if docker image inspect "$IMAGE" >/dev/null 2>&1; then
  echo "→ image $IMAGE already built (delete it to force rebuild)"
else
  echo "→ docker build -f docker/Dockerfile -t $IMAGE ."
  docker build -f docker/Dockerfile -t "$IMAGE" .
fi

# 3. Deploy the stack. Idempotent: docker stack deploy converges to desired state.
echo "→ docker stack deploy -c docker/docker-stack.yml $STACK"
docker stack deploy -c docker/docker-stack.yml "$STACK"

echo
echo "✅ Stack '$STACK' is up. Try:"
echo "   ./scripts/demo-run.sh 'Your prompt here.'"
echo "   ./scripts/demo-logs.sh"
