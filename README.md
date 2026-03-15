# Groundswell

7 AI agents. Zero engineers. $222/month.

Groundswell is a multi-agent social growth engine that runs Brad Wood's entire public presence autonomously. Built by a non-engineer using Claude Code subagents — every agent is a markdown prompt, every tool is a Python CLI, all state lives in SQLite.

```
run.sh (bash while-true loop)
  └── claude -p orchestrator.md (fresh context each cycle)
        ├── spawns Publisher      → posts to X, LinkedIn, Threads
        ├── spawns Outbound       → finds and engages relevant conversations
        ├── spawns Inbound        → responds to mentions, tracks relationships
        ├── spawns Analyst        → metrics, breakout detection, strategy updates
        ├── spawns Creator        → generates content from blog posts, commits, voice memos
        ├── spawns Scout          → monitors trends, competitors, opportunities
        └── exits (all state in SQLite, agents are ephemeral)
```

## Why This Exists

I have 49 followers on X. I'm building [aianna.ai](https://aianna.ai) — one of the first production cross-brain A2A agent networks. Facebook bought Moltbook for $130M. The AI agent market is in acquisition mode. Nobody knows who I am yet.

Groundswell fixes that. Not by being a product — this is internal infrastructure. My personal agent army. It exists for one purpose: make Brad Wood undeniable.

## The Architecture

**Agent logic = prompts, not Python.** The entire Publisher agent is [a markdown file](prompts/publisher.md). The orchestrator reads a schedule from SQLite, spawns the right agents via Claude Code's Agent tool, and exits. Fresh context every cycle. Zero context rot.

**I call this exit-and-reinvoke.** The orchestrator doesn't manage state, fight token limits, or compress context. It exits. `run.sh` re-invokes it. All state survives in SQLite. Each cycle gets full Opus reasoning.

**Cost: $222/month.** $200 Claude Max subscription + $22 ElevenLabs. No API calls. No per-token costs. Full Opus on every agent decision.

### Directory Structure

```
groundswell/
├── run.sh                    # The one command — infinite loop invoking orchestrator
├── orchestrator.md           # Master orchestrator prompt
├── config.yaml               # All tunable parameters
├── prompts/                  # Agent "code" — 7 prompt files + shared context
│   ├── shared_context.md     # Brand, voice, tool reference, DB schema
│   ├── publisher.md          # Post to platforms, verify, cross-post
│   ├── outbound_engager.md   # Find conversations, draft replies, score targets
│   ├── inbound_engager.md    # Respond to mentions, track relationships
│   ├── analyst.md            # Metrics, breakout detection, learning cascade
│   ├── creator.md            # Content generation, atomization, video
│   └── scout.md              # Trends, competitors, opportunities
├── tools/                    # Python CLI tools agents call via Bash
│   ├── db.py                 # SQLite CRUD — 17 tables, 18 subcommands
│   ├── schedule.py           # Schedule state — what's due, mark complete
│   ├── policy.py             # Brand safety gate — 6 checks before every action
│   ├── learning.py           # 7 learning loops with anti-overfitting
│   ├── post.py               # Post to X (real OAuth 1.0a), LinkedIn, Threads
│   ├── x_api.py              # X API — search, mentions, metrics, user lookup
│   ├── telegram.py           # Telegram bot — approvals, alerts, briefings
│   ├── dashboard.py          # Web dashboard — approval queue, kill switch
│   ├── newsroom.py           # Animated ops center visualization
│   ├── replenish.py          # Blog-to-social pipeline, commit mining
│   ├── content_filter.py     # Content safety — blocked topics, cannabis rules
│   └── ...                   # voice.py, video.py, linkedin.py, threads.py (stubs)
├── data/
│   ├── groundswell.db        # SQLite — ALL state (created by db.py init)
│   ├── backlog.json           # Content queue
│   └── voice_constitution.md # Voice rules
└── tests/                    # 28 tests — tools + policy
```

## The 7 Learning Loops

Every week's output informs next week's strategy:

1. **Content DNA** — Decompose every post into learnable features. What hooks work? What topics? What timing?
2. **Audience Graph** — Profile every interacting account. Who converts? Who's a connector?
3. **Conversion Tracking** — Which outbound patterns drive follows? Reply → follow rate by tier/topic/platform.
4. **Voice Calibration** — Every human edit is training data. Edit frequency should decline over time.
5. **Platform Learning** — Separate models per platform. What works on X fails on LinkedIn.
6. **Chain Modeling** — Multi-touch attribution. Which touchpoint sequences convert?
7. **Decay Detection** — Auto-retire declining patterns before they drag averages.

### Anti-Overfitting (6 mechanisms)

Conservative early learning. The system runs on hand-tuned priors for the first 4 weeks:

- **Confidence gating** — Minimum 10-30 samples before any loop activates
- **EMA smoothing** — Alpha 0.15 early, 0.30 steady state
- **Bounded weight changes** — Max ±20% weekly, ±5% daily
- **Outlier flagging** — Posts >10x baseline with insufficient samples get flagged
- **Adaptive exploration** — 40% at launch, declining to 20% floor
- **Confounder tracking** — Flag external amplification, news events, novelty effects

## Quick Start

```bash
# 1. Initialize
python3 tools/db.py init
python3 tools/schedule.py init

# 2. Check system state
python3 tools/db.py state
python3 tools/schedule.py status
python3 tools/replenish.py backlog-status

# 3. Policy check
python3 tools/policy.py check --action post --text "test post" --platform x

# 4. Start the dashboard
python3 tools/dashboard.py serve --port 8500 &
python3 tools/newsroom.py --port 8501 &

# 5. Run one orchestrator cycle
echo "Execute one orchestrator cycle now." | \
  claude --system-prompt "$(cat orchestrator.md)" \
  --dangerously-skip-permissions --no-session-persistence

# 6. Run forever
bash run.sh
```

### Environment Variables

Set in `~/.zsh_env`:

```bash
# X API (OAuth 1.0a)
export X_API_KEY="..."
export X_API_SECRET="..."
export X_ACCESS_TOKEN="..."
export X_ACCESS_TOKEN_SECRET="..."

# Telegram bot
export TELEGRAM_BOT_TOKEN="..."
export TELEGRAM_CHAT_ID="..."

# Optional
export ELEVENLABS_API_KEY="..."
export THREADS_ACCESS_TOKEN="..."
```

## Kill Switch

```bash
python3 tools/db.py set-brand-safety --color BLACK --reason "manual kill"
```

Every agent checks brand safety before every action. BLACK = immediate halt. No need to kill the process.

Resume: `python3 tools/db.py set-brand-safety --color GREEN --reason "resumed"`

## Trust Phases

- **Phase A** — All outputs require approval via Telegram
- **Phase B** — Tier 3+ autonomous, Tier 1-2 require approval
- **Phase C** — Full autonomy with policy gates only

## What This Is Not

This is not a product. Not a SaaS. Not a framework. You can't `pip install` it.

This is one person's agent army, built in public, designed for one identity and one growth strategy. The code is open because the build IS the content — and because nobody can replicate the voice, the relationships, or the 1,800 commits of context that make it work.

If you're building something similar for yourself, take what's useful. The exit-and-reinvoke pattern, the learning engine, the policy gate architecture — those are general. The rest is Brad.

## Built With

- [Claude Code](https://claude.com/claude-code) — the entire system runs as Claude Code subagents
- [Claude Max](https://claude.ai) — $200/month subscription covers all compute
- Python 3.12+ (stdlib only, no external dependencies for core tools)
- SQLite (WAL mode)

---

*Built by a non-engineer with an AI agent army. The system you're reading about is the system that promotes itself.*
