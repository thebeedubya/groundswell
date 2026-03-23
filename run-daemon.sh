#!/bin/bash
# Wrapper for launchd — sources credentials and PATH then runs the engine
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/Users/bradwood/.local/bin:/Users/bradwood/Library/Python/3.9/bin:$PATH"
export HOME="/Users/bradwood"
source ~/.zsh_env 2>/dev/null
cd /Users/bradwood/Projects/groundswell
exec bash run.sh
