#!/bin/bash
# Groundswell — Social Growth Agent Network
# This is the only command needed: bash run.sh
# It loops forever, invoking the orchestrator on schedule.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Ensure data directories exist
mkdir -p data/logs

# Initialize DB and schedule if needed
python3 tools/db.py init 2>/dev/null
python3 tools/schedule.py init 2>/dev/null

LOG_DIR="data/logs"

while true; do
    # How long until next task?
    SLEEP_SECS=$(python3 tools/schedule.py next-sleep 2>/dev/null || echo 60)

    # Cap at 5 minutes
    [ "$SLEEP_SECS" -gt 300 ] && SLEEP_SECS=300

    sleep "$SLEEP_SECS"

    # Run one orchestrator cycle
    LOG_FILE="$LOG_DIR/orchestrator-$(date +%Y-%m-%d).log"
    echo "--- $(date -u +%Y-%m-%dT%H:%M:%SZ) ---" >> "$LOG_FILE"

    # Pass orchestrator.md as system prompt, "run" as the task via stdin
    # Follows the leroy pattern: --system-prompt for persona, stdin for instruction
    echo "Execute one orchestrator cycle now. Follow your system prompt instructions exactly." | \
        claude \
            --system-prompt "$(cat orchestrator.md)" \
            --dangerously-skip-permissions \
            --no-session-persistence \
            >> "$LOG_FILE" 2>&1

    EXIT_CODE=$?
    if [ $EXIT_CODE -ne 0 ]; then
        echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) orchestrator exited with code $EXIT_CODE" >> "$LOG_FILE"
    fi
done
