#!/usr/bin/env bash
# Live-watch agent services spinning up and down. Run in a second pane.
# Usage: ./scripts/demo-logs.sh
set -euo pipefail

WATCH_INTERVAL="${AGENT_SWARM_LOGS_INTERVAL:-1}"

if ! command -v watch >/dev/null 2>&1; then
  echo "Warning: 'watch' not found; falling back to a poll loop." >&2
  while true; do
    clear
    docker service ls --filter "label=agent-swarm.role" \
      --format 'table {{.ID}}\t{{.Name}}\t{{.Replicas}}\t{{.Image}}'
    sleep "$WATCH_INTERVAL"
  done
fi

# Show the supervisor (long-lived) + every ephemeral agent service spawned
# during a run. The label filter keeps unrelated services out of the view.
exec watch -n "$WATCH_INTERVAL" --no-title \
  "docker service ls --filter 'label=agent-swarm.role' \
   --format 'table {{.ID}}\t{{.Name}}\t{{.Replicas}}\t{{.Image}}'"
