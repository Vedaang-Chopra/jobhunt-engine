#!/bin/bash
# Dedicated automation Chrome for job-hunt LinkedIn sweeps.
#
# Runs the job-hunt browser profile (LinkedIn-logged-in) with a DevTools
# endpoint on :9333 so every sweep and the Playwright MCP attach to ONE
# shared logged-in browser. Idempotent: skips launch when :9333 already
# answers. Logs to $HOME/.hermes/browser-profiles/automation_chrome.log.
#
# Cross-platform (macOS + Linux). On Linux set CHROME_BIN if Chrome is not
# auto-detected, e.g.:  export CHROME_BIN=/usr/bin/google-chrome-stable
set -u

PROFILE="$HOME/.hermes/browser-profiles/job-hunt"
PORT=9333
LOG="$HOME/.hermes/browser-profiles/automation_chrome.log"

# Chrome needs an X display for a visible window; under systemd the user
# manager may not carry DISPLAY. Default to the first local display.
if [ "$(uname -s)" = "Linux" ] && [ -z "${DISPLAY:-}" ]; then
  for d in :1 :0; do
    if [ -S "/tmp/.X11-unix/X${d#:}" ]; then export DISPLAY="$d"; break; fi
  done
fi

mkdir -p "$PROFILE"

# ---- locate a Chrome/Chromium binary for this OS -------------------------
find_chrome() {
  if [ -n "${CHROME_BIN:-}" ] && [ -x "$CHROME_BIN" ]; then
    echo "$CHROME_BIN"; return 0
  fi
  local candidates=()
  case "$(uname -s)" in
    Darwin)
      candidates=(
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        "/Applications/Chromium.app/Contents/MacOS/Chromium"
      )
      ;;
    Linux)
      candidates=(
        "/usr/bin/google-chrome-stable"
        "/usr/bin/google-chrome"
        "/usr/bin/chromium"
        "/usr/bin/chromium-browser"
        "/snap/bin/chromium"
        "/usr/bin/microsoft-edge"
      )
      ;;
  esac
  local c
  for c in "${candidates[@]}"; do
    if [ -x "$c" ]; then echo "$c"; return 0; fi
  done
  return 1
}

CHROME="$(find_chrome)" || {
  echo "[automation-chrome] ERROR: no Chrome/Chromium binary found." | tee -a "$LOG"
  echo "  Install google-chrome-stable or set CHROME_BIN." | tee -a "$LOG"
  exit 1
}

if curl -sf --max-time 2 "http://127.0.0.1:${PORT}/json/version" >/dev/null 2>&1; then
  echo "[automation-chrome] already serving CDP on :${PORT}"
  exit 0
fi

# Refuse when the profile is held by another Chrome without our CDP port
# (e.g. the Playwright MCP launched it via remote-debugging-pipe). Attaching
# would fail with ProcessSingleton; surface that instead of silently failing.
if [ -e "$PROFILE/SingletonLock" ]; then
  echo "[automation-chrome] WARNING: $PROFILE has a SingletonLock." | tee -a "$LOG"
  echo "  Another Chrome may be running this profile without CDP." | tee -a "$LOG"
  echo "  Quit it first (or restart via this script), then re-run." | tee -a "$LOG"
fi

# Linux hardening: --no-sandbox is required inside containers/servers without
# user namespaces; on a normal desktop install it is unnecessary. Detect via
# whether unprivileged userns is usable. Use --headless=never so LinkedIn
# logins behave like a real browser.
EXTRA_FLAGS=()
if [ "$(uname -s)" = "Linux" ]; then
  EXTRA_FLAGS+=(--remote-allow-origins='*' --disable-dev-shm-usage)
  if grep -qsE "max_user_namespaces.*0|unprivileged_userns" /proc/sys/user/max_user_namespaces 2>/dev/null \
     && [ "$(cat /proc/sys/user/max_user_namespaces 2>/dev/null || echo 0)" = "0" ]; then
    EXTRA_FLAGS+=(--no-sandbox)
  fi
fi

nohup "$CHROME" \
  --remote-debugging-port="${PORT}" \
  --user-data-dir="${PROFILE}" \
  --no-first-run \
  --no-default-browser-check \
  ${EXTRA_FLAGS[@]+"${EXTRA_FLAGS[@]}"} \
  >>"$LOG" 2>&1 &

for _ in $(seq 1 20); do
  if curl -sf --max-time 2 "http://127.0.0.1:${PORT}/json/version" >/dev/null 2>&1; then
    echo "[automation-chrome] CDP ready on :${PORT} (${CHROME})"
    echo "$(date '+%F %T') started on :${PORT} via ${CHROME}" >>"$LOG"
    exit 0
  fi
  sleep 1
done

echo "[automation-chrome] ERROR: CDP did not come up on :${PORT} within 20s" | tee -a "$LOG"
exit 1
