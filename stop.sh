#!/usr/bin/env bash
# Stop the Job Hunt UI server.
PIDS=$(lsof -ti :8080 2>/dev/null || true)
if [ -z "$PIDS" ]; then
  echo "UI is not running."
  exit 0
fi
echo "$PIDS" | xargs kill
sleep 1
if lsof -ti :8080 >/dev/null 2>&1; then
  echo "$PIDS" | xargs kill -9 2>/dev/null
  echo "Force-stopped."
else
  echo "Stopped."
fi
