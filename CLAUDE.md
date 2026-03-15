# CLAUDE.md — Groundswell

Groundswell is Brad Wood's multi-agent social growth engine. It is NOT a product — it is internal infrastructure for building Brad's "AI Operator" brand.

## Before You Do Anything

1. Query aianna: `query_memory("Groundswell")` — load all prior architecture decisions, agent designs, and pivots
2. Query lessons: `query_lessons(domain="social-growth")` and `query_lessons(domain="multi-agent")`
3. Read PLAN.md in this repo — it is the authoritative architecture document

## During Work

- **Persist every design decision** to aianna via `persist_append`. Architecture choices, agent boundaries, trade-offs, what was rejected and why.
- **Planning mode sessions are the highest-value content.** If you are in plan mode discussing Groundswell architecture, persist every 5-10 minutes minimum.
- This project changes fast. What you persist now is the only record of WHY decisions were made.

## Key Context

- 7 agents: Orchestrator, Publisher, Outbound Engager, Inbound Engager, Analyst, Creator, Scout
- Policy/Safety is a shared service, not an agent
- Budget: $500/month — local inference where possible, no per-call API costs for routine operations
- Brad's identity: "AI Operator" — non-engineer running 8-figure business with AI agents. Cannabis is proof vertical.
- North star: Advisory pipeline inbound. MJBizCon Jan 2027 speaker slot.
