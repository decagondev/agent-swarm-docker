#!/usr/bin/env bash
# Pentest variant of demo-run.sh. Identical shape; adds --pentest so the
# supervisor exposes the nmap_scan + pentest_reporter agents to the LLM.
# Usage: ./scripts/pen-test-demo.sh "Scan scanme.nmap.org and write a brief."
set -euo pipefail

STACK="${AGENT_SWARM_STACK:-agent-swarm}"
SERVICE="${STACK}_supervisor"

if [[ $# -eq 0 ]]; then
  echo "Usage: $0 \"<prompt>\"" >&2
  exit 2
fi

CONTAINER="$(docker ps \
  --filter "label=com.docker.swarm.service.name=${SERVICE}" \
  --format '{{.ID}}' | head -n1)"

if [[ -z "$CONTAINER" ]]; then
  echo "Error: no running container for service ${SERVICE}." >&2
  echo "Did you run ./scripts/demo-up.sh ?" >&2
  exit 1
fi

echo "→ exec into ${CONTAINER} (service ${SERVICE}) — pentest mode"
exec docker exec -i "$CONTAINER" \
  python supervisor.py --executor swarm --pentest "$@"
