#!/bin/bash
# Groundswell — Social Growth Agent Network
# This is the only command needed: bash run.sh
# It loops forever, invoking the orchestrator on schedule.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Load Telegram credentials for alerts
source ~/.zsh_env 2>/dev/null

# Ensure data directories exist
mkdir -p data/logs

# Initialize DB and schedule if needed
python3 tools/db.py init 2>/dev/null
python3 tools/schedule.py init 2>/dev/null

LOG_DIR="data/logs"
AUTH_FAIL_COUNT=0
AUTH_ALERT_SENT=0

send_telegram() {
    local msg="$1"
    if [ -n "$TELEGRAM_BOT_TOKEN" ] && [ -n "$TELEGRAM_CHAT_ID" ]; then
        curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
            -d chat_id="$TELEGRAM_CHAT_ID" \
            -d text="$msg" \
            -d parse_mode="Markdown" > /dev/null 2>&1
    fi
}

while true; do
    # How long until next task?
    SLEEP_SECS=$(python3 tools/schedule.py next-sleep 2>/dev/null || echo 60)

    # Cap at 5 minutes (unless backing off for auth failure)
    if [ "$AUTH_FAIL_COUNT" -gt 0 ]; then
        # Exponential backoff: 1min, 2min, 4min, 8min, cap at 15min
        BACKOFF=$(( 60 * (2 ** (AUTH_FAIL_COUNT - 1)) ))
        [ "$BACKOFF" -gt 900 ] && BACKOFF=900
        SLEEP_SECS=$BACKOFF
    else
        [ "$SLEEP_SECS" -gt 300 ] && SLEEP_SECS=300
    fi

    sleep "$SLEEP_SECS"

    # Run Python tool tasks directly — these don't need Claude, $0 cost
    DUE_TASKS=$(python3 tools/schedule.py due 2>/dev/null || echo "[]")

    if echo "$DUE_TASKS" | grep -q '"rss_fetch"'; then
        python3 tools/rss_fetch.py fetch >> "$LOG_DIR/rss_fetch.log" 2>&1
        python3 tools/schedule.py complete --task rss_fetch 2>/dev/null
    fi

    if echo "$DUE_TASKS" | grep -q '"approval_triage"'; then
        python3 tools/telegram.py triage >> "$LOG_DIR/triage.log" 2>&1
        python3 tools/schedule.py complete --task approval_triage 2>/dev/null
    fi

    # Execute any approved items (API → Playwright fallback) — every cycle
    python3 tools/approval_executor.py run >> "$LOG_DIR/executor.log" 2>&1

    # Run one orchestrator cycle
    LOG_FILE="$LOG_DIR/orchestrator-$(date +%Y-%m-%d).log"
    echo "--- $(date -u +%Y-%m-%dT%H:%M:%SZ) ---" >> "$LOG_FILE"

    # Capture output to check for auth errors
    CYCLE_OUTPUT=$(echo "Execute one orchestrator cycle now. Follow your system prompt instructions exactly." | \
        claude \
            --system-prompt "$(cat orchestrator.md)" \
            --dangerously-skip-permissions \
            --no-session-persistence \
            2>&1)

    EXIT_CODE=$?
    echo "$CYCLE_OUTPUT" >> "$LOG_FILE"

    if [ $EXIT_CODE -ne 0 ]; then
        echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) orchestrator exited with code $EXIT_CODE" >> "$LOG_FILE"

        # Check if this is an auth failure
        if echo "$CYCLE_OUTPUT" | grep -q "authentication_error\|OAuth token has expired\|Invalid authentication credentials"; then
            AUTH_FAIL_COUNT=$((AUTH_FAIL_COUNT + 1))

            if [ "$AUTH_ALERT_SENT" -eq 0 ]; then
                send_telegram "🚨 *Groundswell Auth Down*
OAuth token expired. Run \`/login\` in Claude Code to restore.
Backing off — next retry in $((60 * (2 ** (AUTH_FAIL_COUNT - 1))))s."
                AUTH_ALERT_SENT=1
            fi

            echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) AUTH FAILURE #${AUTH_FAIL_COUNT} — backing off" >> "$LOG_FILE"
            continue
        fi
    else
        # Successful cycle — reset auth failure state
        if [ "$AUTH_FAIL_COUNT" -gt 0 ]; then
            send_telegram "✅ *Groundswell Auth Restored*
Back online after ${AUTH_FAIL_COUNT} failed attempts."
            AUTH_FAIL_COUNT=0
            AUTH_ALERT_SENT=0
        fi
    fi
done
