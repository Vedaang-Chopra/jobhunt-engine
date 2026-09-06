#!/usr/bin/env bash
# Manage the Job Hunt UI LaunchAgent (com.jobhunt.ui).
# Usage: ./service.sh {start|stop|restart|status|log}
set -euo pipefail
LABEL="com.jobhunt.ui"
DOMAIN="gui/$(id -u)"
PLIST="$HOME/Library/LaunchAgents/${LABEL}.plist"
LOG="$HOME/Library/Logs/jobhunt-ui.log"

case "${1:-status}" in
  start)
    launchctl bootout "$DOMAIN/${LABEL}" 2>/dev/null || true
    launchctl bootstrap "$DOMAIN" "$PLIST"
    echo "Started $LABEL — http://localhost:8080 (log: $LOG)"
    ;;
  stop)
    launchctl bootout "$DOMAIN/${LABEL}" 2>/dev/null && echo "Stopped." || echo "Not running."
    ;;
  restart)
    launchctl kickstart -k "$DOMAIN/${LABEL}"
    echo "Restarted — http://localhost:8080"
    ;;
  status)
    if launchctl print "$DOMAIN/${LABEL}" >/dev/null 2>&1; then
      launchctl print "$DOMAIN/${LABEL}" | grep -E 'state|pid' | head -4
      curl -sf -o /dev/null http://localhost:8080 && echo "HTTP OK at http://localhost:8080" || echo "Not answering on :8080 yet"
    else
      echo "Not loaded."
    fi
    ;;
  log)
    tail -n "${2:-50}" "$LOG"
    ;;
  *)
    echo "Usage: ./service.sh {start|stop|restart|status|log [n]}"
    exit 1
    ;;
esac
