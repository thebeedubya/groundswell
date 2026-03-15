# Groundswell — Social Growth Agent Network

## Context

Brad Wood (44 followers on X) is building aianna.ai with co-founder Carric Dooley — one of the first production cross-brain A2A agent networks. The AI agent/tooling market is in full acquisition mode: Facebook bought Moltbook (OpenClaw) for $130M, Bolt $130M, Cursor $2.5B. The train has left the station. Brad and Carric are doing cutting-edge work that most acquirers can't build internally — but nobody knows yet.

The current `tools/social/autopilot.py` is a monolithic cron loop — one process doing 8+ things with no retry, no verification, a jitter bug killing 94% of posts. It lives inside forge-ecosystem with no separation of concerns.

**This is a full redesign as a standalone multi-agent growth engine.** New repo at `~/Projects/groundswell/`. An orchestrator with 7 specialized subagents, each owning ≤3 responsibilities, plus a Policy/Safety shared service. Not a content distribution engine — a machine that makes Brad Wood a known name in AI.

**Groundswell is NOT a product.** It's not OpenClaw, not Typefully, not Buffer. Facebook bought Moltbook for $130M and the fast followers (Perplexity, Computer Use, co-work) are all racing to be the next "AI social media tool." Let them. That's a race to commodity. Groundswell is internal infrastructure — Brad's personal agent army. Nobody else uses it. Nobody buys it. It exists for one purpose: make Brad Wood undeniable. The companies building AI social tools sell picks and shovels. Brad mines the gold.

**The meta-narrative:** Groundswell IS the proof. The growth engine itself demonstrates the thesis — you don't need a human army, you need an agent army. Every piece of content it produces, every follower it gains, every platform it manages autonomously is a receipt. The medium is the message. "My competitors in the AI social space got acquired for $130M building tools. I didn't build a tool — I built an agent army that runs my entire public presence. That's the difference between building AI products and being an AI Operator."

**End state:** Brad Wood = "the non-engineer running an 8-figure business with 7 people and an army of AI agents." Advisory pipeline opens at 20K+ followers. The system itself is the proof.

**NORTH STAR: Inbound.** Brad's phone blows up with executives asking for help scaling AI operations that aren't toys. Cannabis is the wedge (it's Brad's vertical and the hardest proof of concept). But the advisory pipeline is industry-agnostic — any executive sitting on bloated headcount and shrinking margins who knows AI should be solving it but can't make it work in production. The content engine makes Brad findable. The receipts make Brad undeniable. MJBizCon January 2027 is a milestone on this path, not the destination.

**Brad's daily commitment: 30 minutes + 2 voice memos. The system does everything else.**

## Project: `groundswell`

New repo: `~/Projects/groundswell/`
Independent of forge-ecosystem. Copies needed modules from `tools/social/` into its own tree. Own git repo, own venv, own launchd plist.

---

## Positioning: AI is the Identity, Cannabis is the Proof

**The strategic answer:** Brad is "The AI Operator." Cannabis is the hardest, most credible proof point — not the ceiling.

**Why this framing wins:**
- **No boxing out.** "AI Operator" is industry-agnostic. Healthcare execs, logistics CEOs, cannabis operators all see themselves in the story. Cannabis proves it works in the hardest environment; if it works there, it works anywhere.
- **Cannabis = moat, not ceiling.** Anyone can demo AI agents on a todo app. Running them in a federally illegal, state-by-state regulated industry with compliance nightmares is 10x more credible than ChatGPT wrappers.
- **Advisory pipeline stays wide.** Inbound comes from cannabis execs (LinkedIn) AND AI/tech execs (X). Both paths lead to the same offer: "I'll show you how to run an agent-first operation."
- **Hormozi model.** He's "the business guy" — gyms are his proof vertical. Nobody calls him "the gym guy." Cannabis does the same for Brad.

**Content routing principle:** Lead with AI Operator everywhere. Prove with cannabis on LinkedIn. Bridge on both platforms when the content naturally crosses ("here's what happens when you run AI agents in the most regulated industry in America").

---

## The Brand (everything flows from this)

### The Villain

**Two villains for two audiences:**

**For AI/tech audience:** The human army model. Cardone has 200 people. Gary Vee has a 30-person content team. Alex is spending millions trying to retrofit AI onto a human org chart. Brad's counter: "You don't need an army of people. You need an army of smart agents. I started with zero and built the whole thing from Day 1."

**For cannabis audience:** Operational overhead that steals your best people from doing their best work. The compliance grind, the inventory tracking, the reporting burden that has nothing to do with growing great cannabis. The villain is NOT headcount — cannabis operators are fiercely loyal to their people and that loyalty is a virtue. The villain is the GRIND that buries talented people in paperwork.

**Cannabis messaging (critical — get this wrong and you're locked out):**
- "Your people are incredible. They're also drowning in compliance paperwork that has nothing to do with growing great cannabis. AI agents handle the grind so your team does what they're actually good at."
- "You're stuck at $2M because your best grower spends 30% of their time on compliance docs. AI agents give them that time back."
- "You want to go from 3 sites to 7 but you can't hire fast enough and margins won't support it. AI agents let you scale without doubling headcount."
- "Your team IS your competitive advantage. Stop wasting them on tasks a machine should handle."

**The cannabis audience is NOT 25 MSO CEOs.** MSOs have outsized reach but are often outsiders in the ecosystem. The real power base is hundreds of 1-10 site operators who crush with quality and marketing, make millions, and are industry heroes. They don't have big-company operational sophistication — that's the gap. They need growth + operational excellence WITHOUT betraying the people who built their business.

**NEVER say:** "replace your staff," "cut headcount," "fire your compliance team." Always say: "free your team," "scale without adding overhead," "let your people do what they're best at."

At 20K followers, the tech grenade still works for the AI audience: "Cardone has 200 people producing his content. I have zero. My AI agents did it all." But for cannabis, the message is always: "grow bigger, operate cleaner, keep your people."

### The Identity

**One-sentence identity:** "Non-engineer running an 8-figure business with 7 people. The rest of the workforce is AI agents. 1,800 commits/year."

**Category creation:** "AI Operator" — not an engineer, not a PM, not a consultant. Someone who builds and runs AI agent infrastructure to operate a business. This category barely exists. Own it.

**Named frameworks Brad owns:**
- **Cross-Brain Architecture** — two AIs sharing memory across organizations via A2A (name this before someone else does)
- **Agent-First Operations** — AI agents are primary operators, humans are the escalation path
- **The FORGE Pattern** — how a non-engineer builds production AI infrastructure
- **Operator Leverage** — FTE-equivalents handled by agents vs humans ("my 7-person company operates like a 40-person company")

### The Movement

Not a following — a movement. "AI Operators" — people who build and run AI systems without being engineers.
- Manifesto thread (the Day 1 post)
- Shared identity ("I'm an AI Operator")
- Us vs them (builders vs talkers, operators vs consultants)
- Call to action beyond "follow me" ("Build your own agent system this weekend. Here's exactly how.")

### Visual Gravity

Dark terminal aesthetic = Brad's visual signature. Systematized:
- Every video: same terminal color scheme, same font, same vibe
- Every screenshot: same crop, same dark background
- Consistent across all platforms — when people see dark terminal with AI reasoning, they think Brad Wood before reading the handle

### Signature Formats

**"FORGE Dispatch"** — weekly thread showing actual system output. What the agents did, decided, and what surprised Brad. Real terminal screenshots, real agent conversations, real numbers. Nobody else can create this content.

**"Commit of the Day"** — daily post showing one interesting commit and the story behind it. Low effort, high authenticity.

**"Leverage Report"** — monthly metrics: headcount, agent-hours, tasks automated, commit count. No financials.

### The Breakout Thread (engineered moment)

"Last year, Stripe's CEO Patrick Collison made 950 commits. People lost their minds. A CEO who still builds.

I made 1,800.

But here's the thing — I'm not an engineer. I run an 8-figure business with 7 people. The other 'employees' are AI agents I built and manage through an operating system called FORGE.

Cardone has 200 people producing his social content. I have zero. My AI agents do it all.

Here's what 1,800 commits looks like when your workforce is human + AI:

[Thread continues with commit breakdowns, terminal screenshots, leverage ratios, the 7-person stack]"

### Privacy Constraint

Family office = no specific financials. Safe to say:
- "8-figure revenue" (range, not number)
- "7 people" (headcount = structure, not financials)
- Commit count (public GitHub)
- Operational ratios ("agents handle 80% of workflows")
- Time metrics ("2 hours/week on what used to take 40")

Never say: specific revenue, ARR, customer count, deal sizes, growth rates, margins.

### Dual-Vertical Strategy: AI + Cannabis

Brad isn't just an "AI Operator." He's **the AI Operator who's transforming cannabis operations.** The intersection has zero competition.

**For the AI audience:** Brad runs AI agents in a heavily regulated, operationally complex industry. If it works in cannabis, it works anywhere. 10x more credible than chatbot demos.

**For the cannabis audience:** Brad speaks their language AND has the tech edge nobody else in the room has. When Kim Rivers or Shadd Dale sees Brad's content, they see someone who gets cannabis AND has built the future.

**Content routing:**
| Content Type | Primary Audience | Primary Platform |
|---|---|---|
| AI agent architecture, FORGE internals | AI/tech | X |
| Cannabis operations opinions, industry takes | Cannabis execs | LinkedIn |
| "How AI agents handle cannabis compliance" | BOTH (cross-pollination) | X + LinkedIn |
| Terminal screenshots, agent reasoning | AI/tech | X, YouTube Shorts |
| "The 7-person stack for cannabis operations" | Cannabis execs + VCs | LinkedIn |
| Operations Autopsy (public MSO earnings) | Cannabis | LinkedIn |
| Compliance Agent Demo (video) | Both | LinkedIn + X |
| Cannabis AI Playbook (give away free) | Cannabis | LinkedIn, blog |
| Contrarian cannabis take | Cannabis | LinkedIn |

**LinkedIn is a PRIMARY platform, not secondary.** Cannabis executives live on LinkedIn. Cannabis content goes to LinkedIn FIRST.

### Cannabis Tier 1 Targets

**Cannabis Tier 1 (5-10):**
- Kim Rivers (Trulieve CEO)
- Shadd Dale
- Key voices at Curaleaf, Green Thumb, Cresco
- Cannabis tech founders (Dutchie, Treez, Metrc, Aroya ecosystem)
- Industry media (MJBizDaily editors, Cannabis Business Times)
- Conference organizers (MJBizCon, Benzinga Cannabis)

**Cannabis Tier 2 (15-20):**
- State-level operator CEOs
- Cannabis consultants and advisors with large followings
- Aroya ecosystem contacts
- Cannabis VCs and investors

Engager treats cannabis Tier 1 with EQUAL priority to AI/tech Tier 1. Cannabis first, AI second in the engagement voice — sound like a cannabis operator who happens to have AI expertise.

### The Cannabis Villain (Operational Overhead, NOT Headcount)

"The cannabis industry's best people are buried in operational overhead that has nothing to do with growing great cannabis."

Hot takes that resonate with 1-10 site operators:
- "Your head grower is spending 30% of their week on compliance documentation. That's not a compliance problem — that's an operations problem. AI agents give them that time back."
- "You want to expand from 3 sites to 7. You don't need to double your team. You need infrastructure that scales without doubling overhead."
- "The cannabis industry has the most passionate, loyal operators of any industry I've worked in. Why are we burying them in spreadsheets?"
- "Every dollar you spend on operational overhead that an AI agent could handle is a dollar you're not spending on quality, marketing, or your people."
- "I'm not here to tell you to fire anyone. I'm here to show you how to grow from $2M to $10M without hiring 40 more people. Here's how." [terminal screenshot]
- "The cannabis industry doesn't need more consultants. It needs operators who've actually built the infrastructure. I'm showing my work."

### The Aroya Angle

Brad's position at Aroya is the trojan horse — already inside the industry. Content references cultivation operations insights to establish credibility: "In my work with cultivation operations, I've seen..." (without violating confidentiality).

### Cannabis Content Formats

- **"Operations Autopsy"** — take a public MSO's earnings report, identify operational bloat, explain how AI agents solve it
- **"Compliance Agent Demo"** — terminal video of FORGE handling a compliance workflow, ElevenLabs voiceover
- **"The Cannabis AI Playbook"** — free, comprehensive how-to. The Hormozi play for cannabis.
- **"Why Your MSO Needs 50 People, Not 500"** — the contrarian thread for LinkedIn

### MJBizCon Reverse-Engineering Timeline

**March-April 2026 (NOW):**
- Cannabis LinkedIn presence starts (3-5 posts/week)
- Engage with MJBizDaily, Cannabis Business Times
- Get on Shadd Dale's radar through consistent valuable engagement
- Start "Operations Autopsy" series
- Target: 500 followers, Kim Rivers has seen Brad's name 3+ times

**May-June 2026:**
- Speak at a smaller cannabis event (regional conference, Aroya user event, webinar)
- Guest on 2-3 cannabis podcasts (fresh angle: "The AI Operations Guy")
- Publish the Cannabis AI Playbook (free) — cannabis media picks it up
- Target: 2K followers, 2 podcast appearances, 1 speaking clip

**July 2026: MJBizCon Submission**
- Talk title: "7 People, 1,800 Commits, Zero Engineers: How AI Agents Run My Cannabis Operations"
- Application includes: social proof, podcast clips, speaking clip, endorsements from Tier 1 contacts
- Killer differentiator: "Live demo on stage — real terminal, real agents, real compliance workflow"
- Most MJBizCon talks are PowerPoints. Brad shows a live system. Nobody forgets that.

**August-December 2026:**
- Keep building regardless of acceptance
- Benzinga Cannabis Conference (easier slot, same audience) as backup
- Stack speaking gigs, build relationships with past MJBizCon speakers
- If waitlisted: request panel slot, host side event, get IN the building

**January 2027: MJBizCon**
- Brad on stage, terminal running live
- AI agents handling real work while Brad narrates
- Every MSO executive in the room thinking "I need to talk to this guy"
- Advisory pipeline explodes

### Cool Kids Club Infiltration

The cannabis industry is relationship-driven, not follower-driven. Small industry, everyone knows everyone.

**Be useful before you're known.** Comment on Kim Rivers' earnings call with an operational insight she hasn't heard. Don't lead with AI — lead with cannabis operations knowledge.

**Warm intro chain:**
```
Brad → Aroya contacts → Cultivator network → MSO ops leaders → C-suite
```
Each step is a relationship the Engager nurtures. Not selling — adding value.

**Show up where they show up:**
- Cannabis LinkedIn (primary watercooler)
- MJBizDaily comments
- Regional cannabis events
- Benzinga Cannabis Conference
- Industry Slack channels and Discord servers

---

## Approval UX: Slack Bot (`lib/slack_bot.py`)

**Slack is the interface between the agent army and Brad's 30 minutes.** Not terminal, not web UI, not email. Consortium unanimous.

### Daily Morning Briefing (8:00am CT)
One consolidated message, not 40 separate notifications:
- Today's 3 highest-value original posts (approve/edit/reject)
- Top 5 proposed outbound replies (approve/reject)
- Any risky items flagged by Policy (with explanation why flagged)
- System status: trust phase, brand safety state, overnight activity summary
- Relationship backlog count (pending DMs, follow-ups)

### Per-Item Actions (Slack Block Kit)
Each item shows: platform, text, confidence score, risk label, source context.
- **Approve** — adds to queue, posts at scheduled time
- **Edit** — opens Slack modal for inline text edit, then approve
- **Reject + Feedback** — dropdown: "Wrong Voice," "Bad Take," "Off-Topic," "Too Risky." Structured feedback feeds back to Creator/Analyst for tuning.
- **Pause Platform** — halt all activity on one platform

### Emergency Controls (Slack bot home tab)
- **PAUSE ALL** — giant red button. Sets brand safety to RED. All posting stops immediately.
- **Resume** — clears to GREEN after Brad confirms.
- **Override** — during YELLOW state, force-approve a specific item.

### What Auto-Sends Without Slack (Trust Phase C only)
- Cross-platform adaptations of already-approved content
- Tier 3 engagement replies (quality-gated, voice-scored >3.5)
- Metrics/milestone posts
- Reply-to-replies on Brad's own posts (low-risk acknowledgments)
- Commit of the Day posts

### Review Volume Target
Brad reviews ~10 items/day max. If system generates more review-required items, Policy tightens auto-approve thresholds. Never overwhelm Brad — notification fatigue kills adoption.

---

## Operating Model: 30 Minutes + 2 Voice Memos

### Brad's Daily Input (30 min total)
- **5 min:** Morning scan — review the 2-3 items system flagged for approval, approve/reject
- **20 min:** Personal Tier 1 engagement — study their posts, write thoughtful replies that show Brad actually read and understood. This is relationship building, not content production. Cannabis is relationship-driven; 5 minutes doesn't cut it.
- **5 min + 2 voice memos:** Raw thoughts when something interesting happens ("my agent just did X" — 30 seconds into phone)

Everything else is autonomous. 40+ content touchpoints per day without Brad.

### Approval Tiers

```
AUTO-SEND (zero human review, ~80% of content):
├── Cross-platform adaptations of already-approved content
├── Tier 3 engagement replies (quality-gated by Engager policy)
├── Tier 3 quote tweets (quality-gated)
├── Metrics/milestone posts ("Week 8 commit count: 412")
├── Reply-to-replies on Brad's own posts
├── Video clips from pre-approved terminal recordings
├── Commit of the Day posts
└── Content atomized from previously-approved moments

BRAD REVIEWS BEFORE SEND (~15% of content):
├── ALL Tier 1 and Tier 2 engagement (replies, QTs, comments) — one bad AI reply to Kim Rivers burns the relationship permanently
├── Newsjack takes (30-min window — auto-sends if Brad doesn't respond, speed > perfection)
├── Contrarian/controversial takes (higher risk)
├── Cannabis-specific opinion content (industry nuance matters)
├── First use of a new content format
└── Manifesto/movement content

NEVER AUTO-SEND:
├── The Day 1 manifesto post (one-time, Brad writes)
├── Podcast pitch emails
├── DMs to Tier 1 accounts
└── Anything that could expose financials
```

### Voice Memo Pipeline (`lib/intake.py`)

Brad speaks into phone (30 sec) →
1. Whisper transcription
2. Claude drafts: tweet + thread + LinkedIn post + video script
3. FORGE log pull for relevant terminal screenshots
4. ElevenLabs synthesizes voiceover for video version
5. All versions queued to Publisher with platform-native formatting
6. Auto-send (voice-memo content = pre-approved by nature)

30 seconds of Brad's time → 6-8 pieces of content across 5 platforms.

### Content Atomization Pipeline

One raw moment → 10 platform-native pieces (autonomous):

```
1 raw moment (voice memo or system-mined event)
  → Tweet (sharp, hot-take version)
  → Thread (expanded story with context)
  → LinkedIn post (business implications framing)
  → Threads post (personal/conversational version)
  → 60-sec video (terminal recording + ElevenLabs voiceover)
  → YouTube Short (same video, different hook)
  → Quote-tweet of own content (adding follow-up insight)
  → Reply comment on related Tier 1 conversation
```

Daily volume math:
```
2-3 raw moments × 7 adaptations    = 14-21 original posts
+ 15-20 engagement replies          = autonomous (Engager)
+ 3-5 quote tweets                  = autonomous (Engager)
+ 2-3 Commit of the Day posts       = autonomous (Analyst data)
+ 1-2 metric/milestone posts        = autonomous (Analyst)
+ 1 video clip                      = autonomous (Creator)
                                    ≈ 36-50 daily touchpoints
```

Brad's input for this: 60 seconds of voice memos + 30 min review/engagement. The 200-person-team output, zero-person team.

**Volume ramp-up (avoid platform spam flags):**
Week 1: 10-15 touchpoints/day (establish natural-looking activity)
Week 2: 15-25 touchpoints/day
Week 3: 25-35 touchpoints/day
Week 4+: 35-50 touchpoints/day (full velocity)
Going from 44 followers to 50 daily posts overnight = shadowban risk. Ramp gradually.

**Atomization quality gate:** Not every moment becomes 10 pieces. Only strong moments get full atomization. Weak moments get 2-3 versions max. Volume without substance creates algorithmic fatigue.

### Trust Phases (consortium-driven — NOT day-1 full autonomy)

**Phase A: Assisted Autopilot (Weeks 1-3)**
- Scout, Creator, Analyst fully active (internal only, no public actions)
- Publisher: draft + queue, all posts require Brad approval via Slack
- Outbound Engager: proactive replies only, all require approval
- Inbound Engager: low-risk auto-replies (acknowledgments, thank-yous). All multi-turn threads require approval.
- LinkedIn: Playwright posting with Brad approval
- Threads: optional, low priority
- **Goal:** Prove voice consistency. Zero incidents. Build Brad's trust in the system.
- **Volume:** 10-15 touchpoints/day

**Phase B: Selective Autonomy (Weeks 4-6)**
- Low-risk original posts can auto-publish (Tier 3 replies, evergreen content, atomized versions of approved content)
- Outbound Engager expanded: Tier 2+3 replies autonomous, Tier 1 still requires Brad
- Inbound Engager: autonomous for safe categories, escalate for disagreement/adversarial/sensitive
- Crisis detector and Policy hardened based on Phase A learnings
- **Gate:** Only enter Phase B after zero incidents in Phase A
- **Volume:** 20-30 touchpoints/day

**Phase C: Broad Autonomy (Weeks 7+)**
- Only enter after 30-45 days of zero major incidents AND measurable growth
- Brad reviews ~10 items/day (high-risk only), everything else autonomous
- Full cross-platform operation
- Threads engagement automation enabled
- **Volume:** 35-50 touchpoints/day (full velocity)
- **Success metrics that matter:** qualified DMs, speaking/advisory opportunities, engagement rate, zero compliance incidents, voice consistency scores >3.5

### The "No-Touch Day" Target

System can run 24+ hours with zero Brad input. Posting, engaging, responding, newsjacking, creating videos — all autonomous. This is also content:

"I was offline for 36 hours. My AI agents posted 47 pieces of content, engaged with 89 accounts, caught a breaking story, and grew my following by 340. Here's what they did."

### 50/30/20 Rule (Baked Into Orchestrator)

- **50% engagement** with other people's content (Engager: replies, QTs, comments)
- **30% original content** (Publisher: posts, threads, videos)
- **20% brand building** (relationship nurturing, Tier 1 cultivation, podcast tracking)

---

## Agent Decomposition (6 agents, ≤3 responsibilities each)

### 1. Orchestrator (`orchestrator.py`)
The brain. Schedules, coordinates, monitors. Never posts or engages directly.

**Responsibilities:**
1. Priority-queue scheduler (jitter at this level, never in subagents)
2. Cross-agent coordination (signals, circuit breakers, rate limit priority)
3. Health monitoring + escalation (consecutive failures → notification)

**Startup reconciliation (runs on every boot):**
- Check `pending_actions` table for incomplete sends → verify or retry
- Check `platform_cooldowns` table → respect active cooldowns
- Check `strategy_state` table → load current weights
- Check for stale conversation threads → reconcile with API
- Rebuild agent state from durable SQLite, not from lost in-memory signals

**Deadman switch:** If zero actions on any major platform for 24 hours, trigger `ADMIN_ALERT` that bypasses all normal logic → macOS notification.

**Moment amplification:** When Analyst detects a post outperforming by 5x baseline, Orchestrator triggers amplification cascade — Engager follows up, Publisher cross-posts, Creator drafts expansion thread.

**Owns:** Schedule state, agent health state, signal bus
**Talks to:** All subagents via direct import (same process) or subprocess

### 2. Publisher Agent (`agents/publisher.py`)
Gets content out the door. Reliable, verified posting. Handles text, threads, AND video.

**Responsibilities:**
1. Drip posting (time slots, backlog selection, theme weighting) — text, threads, and video
2. Post verification (confirm tweets exist via API)
3. Cross-platform relay (after X post → Threads, LinkedIn)

**Boundary rule:** Publisher changes delivery formatting/mechanics, never meaning/message. Trimming for X character limits = Publisher. Rewriting tone for LinkedIn = Creator.

**Owns:** Backlog lifecycle, pending verification queue, dead letter queue
**Imports from legacy:** `drip.py` functions (load_backlog, save_backlog, current_slot, post_item, etc.), `post.py` (post, post_to_x), `content_filter.py`

### 3. Outbound Engager (`agents/outbound.py`) ⭐ THE GROWTH ENGINE
Hunts for engagement opportunities. Finds conversations to enter. Builds visibility through strategic replies and quote tweets. This is discovery — putting Brad's name in front of new audiences.

**Responsibilities:**
1. Proactive engagement (radar-driven replies to target accounts)
2. Quote tweets (highest leverage for follower conversion)
3. Strategic follow management

**Design philosophy:** Outbound is about being the most interesting person in someone else's replies. One killer reply under a 200K-follower account = worth more than 100 original posts. Quality over quantity. Score many candidates, execute few.

**Tiered targeting system:**
- **Tier 1 (5-10 accounts):** Industry kingmakers (200K+ followers in AI/agent space + cannabis). Every post gets a thoughtful response. QT their best takes. Goal: they notice Brad, follow, eventually co-sign.
- **Tier 2 (20-30 accounts):** Peer builders + mid-tier niche operators (500-5K followers). Where good replies sit near the top. Mutual amplification. Growth cohort.
- **Tier 3 (100+ accounts):** Active community. Selective engagement based on opportunity quality.

**Targeting distribution (consortium insight):**
- 20% Tier 1 giant accounts (visibility)
- 50% Tier 2 mid-tier niche accounts (where replies get seen, conversations happen)
- 30% Tier 3 peer cohort (reciprocal discovery)

**Engagement hierarchy (prioritized):**
1. Tier 1 account posted about agents/A2A/AI ops → respond with insight
2. Quote-tweet with sharp contrarian take (highest growth leverage)
3. Reply-with-insight to Tier 2 accounts (where Brad's reply is visible)
4. Reply-with-question (starts conversation, signals to algorithm)
5. Simple acknowledgment reply (lowest priority)

**Quality gates:**
- Per-cycle: 8 engagements
- Daily cap: 15 outbound (replies + QTs)
- Must add value — "value" includes asking good questions, not just dropping knowledge
- All outbound actions pass through Policy/Safety before execution

**Owns:** Radar scoring, QT opportunity detection, follow strategy
**All actions go through:** `lib/policy.py` before execution

### 4. Inbound Engager (`agents/inbound.py`) ⭐ THE RELATIONSHIP KEEPER
Manages conversations Brad is already in. Reply monitoring, response selection, conversation threading. This is community — nurturing relationships and managing Brad's reputation in real-time.

**Responsibilities:**
1. Reply monitoring (respond to everyone who engages with Brad's posts)
2. Conversation threading (follow-up on conversations gaining traction)
3. DM opportunity flagging (emit `DM_OPPORTUNITY` when target hits 3-touch threshold)

**Risk-tiered operation (consortium-driven):**
- **Low-risk (autonomous):** Simple acknowledgments, thank-yous, non-controversial follow-ups
- **Medium-risk (autonomous with scoring):** Multi-turn replies in safe domains, follow-up questions
- **High-risk (human approval):** Disagreement threads, adversarial conversations, sarcasm detection, legal/compliance language, anything after 2+ turns in sensitive thread

**Thread safety rules:**
- Max 3 automated turns per thread
- Max 2 follow-ups without human response → disengage gracefully
- Adversarial detection → exit with grace templates, escalate to Brad
- Sentiment change detection → if thread turns negative, stop and flag
- Never agree with contradictory points in same thread (context window per-thread)

**Anti-spam policy (shared with Outbound):**
- Cooldown: 4 hours after no response before re-engaging same user
- Never reply more than once to same user within 2 hours unless directly engaged
- Cap: max 5 interactions per target per day, 15 per week
- All actions require idempotency key check before execution

**Relationship carrying capacity (consortium insight):**
Track active conversations, pending follow-ups, unresolved DMs, warm prospects. When backlog exceeds threshold → Outbound Engager reduces proactive volume. System cannot create more social obligations than Brad can fulfill in 30 min/day.

**Owns:** Mention monitoring, conversation state, interaction history, dedup, suppression
**All actions go through:** `lib/policy.py` before execution

### 5. Analyst Agent (`agents/analyst.py`)
Measures everything, **recommends** strategy. Orchestrator distributes, agents consume. Analyst never directly controls execution.

**Responsibilities:**
1. Metrics harvesting (pull engagement data on sent posts)
2. Follower tracking (daily snapshots, velocity calculation)
3. Growth audit + breakout detection (weekly self-optimization AND real-time moment detection)

**Breakout detection (real-time):** When any post exceeds 5x baseline engagement within 2 hours, emit `BREAKOUT_DETECTED` signal. Orchestrator triggers amplification cascade:
- Engager: reply to the post with additional context/thread
- Publisher: immediate cross-platform relay if not already posted
- Creator: draft expansion thread that rides the wave
- Scout: check if the topic is trending and draft follow-up angles

**Growth audit output (weekly):**
- Theme performance ranking → recommends Publisher content selection weights
- Format analysis (tweet vs thread vs QT vs video) → recommends content mix
- Engagement timing → recommends posting slot adjustments
- Follower velocity → triggers strategy escalation if growth stalls
- Tier 1 relationship progress → which kingmakers are engaging back?

**Metric hierarchy (what Analyst optimizes for, in order):**
1. Reputation safety (zero incidents, zero compliance flags)
2. Qualified inbound signals (DMs from operators/investors, podcast invites, advisory asks, speaking requests)
3. Follower growth (right followers, not vanity)
4. Engagement rate (replies > likes > impressions)
5. Volume (last priority — never optimize for output quantity)

**Identity allocation tracking (prevents brand drift):**
- 40% AI Operator / FORGE / agent infrastructure content
- 30% Cannabis proof vertical / domain insights
- 20% Founder/operator lessons / build-in-public
- 10% Personal/human texture
Analyst tracks this ratio weekly. If drift >10% from target, Creator rebalances. Without this, algorithm optimization blurs the positioning.

**Feedback loop stability (prevents oscillation):**
- Bound weight changes: max ±20% shift per audit cycle
- Use EMA (exponential moving average) smoothing, not raw week-over-week
- Preserve minimum 20% exploration allocation (don't starve underperforming themes)
- Log `strategy_version` on every action for later attribution
- Separate short-term metrics noise from strategic shifts

**Owns:** Engagement DB, growth audit history, strategy recommendations
**Imports from legacy:** `engagement_db.py`, `radar.py` (_x_get for metrics)

### 6. Creator Agent (`agents/creator.py`)
Content factory — finds raw material, optimizes it, creates in every format, keeps the backlog full.

**Responsibilities:**
1. Content generation (blog replenish + FORGE system mining + collaboration drafts)
2. Content optimization (hook rewriting, viral format templates, story arc awareness)
3. Video production (terminal recordings + ElevenLabs voiceover — fully autonomous)

**Boundary rule:** Creator changes meaning/message. Publisher changes delivery formatting. Rewriting a hook = Creator. Trimming to character limit = Publisher. Adapting tone for LinkedIn = Creator. Injecting platform metadata = Publisher.

**System mining pipeline (unique differentiator):**
Reads FORGE logs, agent conversations, cross-brain A2A exchanges, sentinel events, and surfaces the most interesting moments as content candidates:
- Agent decision logs showing reasoning chains
- Cross-brain exchanges between Brad's system and Carric's APEX
- Error recovery stories (agent hit a problem, figured it out)
- Performance metrics (tasks automated, hours saved)
- Before/after comparisons (manual process vs agent-handled)
- Unusual agent behaviors ("my agent did something I didn't program it to do")

Each mined moment → drafted as tweet, thread, or video script with Brad's voice.

**Video pipeline (ElevenLabs — fully autonomous):**
Brad's voice is cloned on ElevenLabs. The pipeline:
1. Capture terminal output (asciinema or screen recording of FORGE/agent activity)
2. Generate narration script via Claude ("Watch what happens when my agent on Haze asks Carric's agent on APEX to verify a data point...")
3. Synthesize voiceover via ElevenLabs API in Brad's voice
4. Package as MP4 (terminal recording + voiceover audio)
5. Add to backlog as video content item with platform tags (X, Threads, LinkedIn, YouTube Shorts)

Target: 2-3 terminal videos per week. 60-90 seconds each. Dark terminal aesthetic. Zero human production effort.

**"Failure/Recovery" content (builds executive trust):**
System mining prioritizes stories where the AI FAILED but safety nets caught it. This proves maturity over hype. Cannabis executives need to know: "What happens when the AI hallucinates a compliance filing?" The answer is always: "The agent flagged uncertainty, escalated to a human, and the human caught it in 4 minutes." Humans as escalation path = the safety story that makes executives trust the system.

**Viral format templates:**
- **Contrarian take:** "Everyone is wrong about [X]. Here's why."
- **Numbered insights:** "7 things I learned running AI agents for 6 months"
- **Narrative thread:** "The story of how my AI agent [did something unexpected]"
- **Receipt post:** [Screenshot] + "This is what actually happened when..."
- **Framework post:** "I call this [Named Framework]. Here's how it works."
- **Collaboration thread:** "Brad built X, Carric built Y, here's what happened when they talked"

**Story arc awareness:**
Creator tracks where Brad is in the narrative arc and ensures content reinforces the evolving story:
- Weeks 1-4: "I'm a non-engineer who built an AI operating system. Here's what I'm learning."
- Weeks 5-10: "My agents are now doing things I didn't program. Here's what happened today."
- Weeks 11-20: "We connected two AI brains across the internet. The implications are insane."
- Weeks 21+: "We're open-sourcing the protocol. Here's how to build your own."

**FORGE Dispatch (weekly signature format):**
Every Sunday, Creator auto-generates the weekly dispatch thread:
1. Query FORGE logs for the week's most interesting events
2. Pull metrics (posts sent, engagements, follower delta)
3. Highlight 2-3 agent moments with terminal screenshots
4. Draft thread in Brad's voice with narrative arc context
5. Add to backlog as priority item for Monday morning post

**Collaboration engine (Carric integration):**
- Co-authored thread drafts (Brad's perspective + placeholder for Carric's)
- Tag-team content: Brad posts, draft for Carric to QT with his angle
- Debate threads: genuine technical disagreements played out publicly
- Cross-brain demo content: A2A exchanges formatted as conversation threads

**Owns:** Content generation pipeline, video pipeline, hook optimization state, story arc state
**Imports from legacy:** `replenish.py` patterns, Claude API for generation
**External APIs:** ElevenLabs (voice synthesis), asciinema/ffmpeg (video capture/packaging)

### 7. Scout Agent (`agents/scout.py`) — NEW
Eyes and ears. Detects opportunities before Brad does. Never creates or posts — just surfaces signals.

**Responsibilities:**
1. Trend/news detection (RSS, HackerNews front page, X trending in AI/tech, key account monitoring)
2. Newsjacking opportunities (breaking news → draft take connecting to Brad's work → fast-track to backlog)
3. Opportunity tracking (podcast guest opportunities, conference CFPs, collaboration openings)

**Newsjacking pipeline (the breakout maker):**
1. Monitor sources: RSS feeds (TechCrunch, The Information, AI newsletters), HackerNews front page, X trending topics, Tier 1 account activity
2. Detect relevant event: acquisition, product launch, paper release, controversy in AI/agent space
3. Within 15 minutes: draft a sharp take connecting the news to what Brad is building
4. Fast-track to Publisher backlog as `urgent` priority (skips normal queue)
5. Emit `NEWSJACK_READY` signal → Orchestrator prioritizes posting within 30 min

The Moltbook acquisition should have been caught by Scout before Brad heard about it. That's the bar.

**Tier 1 monitoring:**
Scout watches all Tier 1 account activity. When a kingmaker posts about agents, A2A, or AI operations:
- Emit `TIER1_ACTIVE` signal → Engager prioritizes response
- If the post is QT-worthy, draft a QT and fast-track to Engager

**Podcast/conference tracking:**
- Monitor podcast feeds in AI/tech AND cannabis space for guest opportunities
- Track conference CFPs: AI (AI Engineer, NeurIPS workshops) AND cannabis (MJBizCon, Benzinga, regional)
- **MJBizCon deadline tracking** — speaker submissions, panel opportunities, side events
- Surface opportunities to Brad via notification

**Cannabis news monitoring:**
- MJBizDaily RSS, Cannabis Business Times, Marijuana Moment
- State regulatory agency feeds (new rules = newsjacking)
- Public MSO earnings reports (Trulieve, Curaleaf, GTI, Cresco) — trigger Operations Autopsy content
- Cannabis Tier 1 account activity on LinkedIn
- Cannabis conference announcements

**Owns:** News/trend state, RSS cache, opportunity queue
**External sources:** RSS feeds, HackerNews API, X search API, MJBizDaily, cannabis regulatory feeds

---

## Policy/Safety Shared Service (`lib/policy.py`)

**Not an agent — a shared service that all public-facing actions pass through.** This is the biggest architectural gap the consortium identified. Publisher publishes, Engagers engage, but Policy decides whether any action is safe to execute.

### Brand Safety State Machine

```
GREEN  — Normal ops. Auto-approve safe items, review risky ones.
YELLOW — Heightened caution. All proactive engagement paused. Original posts require extra checks. Triggered by: industry crisis detected, hostile reply volume spike, regulatory topic trending.
RED    — All posting paused except explicit Brad approval. Triggered by: major tragedy, accusation of botting, legal/compliance flag, platform suspension warning.
BLACK  — Account lockdown. Kill switch. Zero outbound. Triggered by: manual Brad override, platform ban, reputation crisis.
```

State transitions logged in events table. Orchestrator checks state before dispatching any task.

### What Policy Evaluates (every outbound action)

1. **Topic safety** — Is this about death, tragedy, politics, layoffs, legal issues, medical claims, addiction, crime, personal allegations? → Block or escalate
2. **Cannabis compliance** — Does this mention specific products, dosing, medical efficacy, interstate commerce, youth use? → Block
3. **Aroya boundary** — Does this imply company positions, leak customer info, reference competitors in ways that create risk? → Escalate to Brad
4. **Stale content check** — Is this draft older than 4 hours? Has the source thread changed materially? → Revalidate or discard (TTL enforcement)
5. **Context conflict** — Is there a major event trending that makes this post tone-deaf? → Hold or escalate
6. **Bait detection** — Is the target account a rage farmer, parody, or sarcasm trap? → Skip
7. **Uncanniness check** — Does this reply sound too polished, too fast, or too perfect for a human? → Add deliberate imperfection or delay
8. **Financial exposure** — Does this reference specific revenue, ARR, customer count, deal sizes, growth rates, margins? → Block always

### Human Cadence Governor (anti-shadowban)

Baked into Policy, not individual agents:
- Randomized delays (5-45 seconds between actions, not instant)
- Energy curve: fewer posts on weekends, more on Tuesday-Thursday
- Deliberate "missed opportunities" — don't reply to every Tier 1 post
- Varied sentence structure and length across consecutive outputs
- No cross-platform posting at identical timestamps
- Rest windows: 2-3 hour gaps with zero activity daily (simulates human offline time)

### Abstention Rule

**No content is better than mediocre content.** Every agent has an explicit "don't act" state with no penalty. If confidence is below threshold, Policy returns `ABSTAIN`. Queue pressure never forces a bad post.

---

## Voice System (`lib/voice.py` — expanded)

**Voice is infrastructure, not an afterthought.** The consortium unanimously agreed: few-shot examples alone drift within 2 weeks at 40+ touchpoints/day.

### Voice Constitution (`data/voice_constitution.md`)
Rules, not examples. What Brad IS and IS NOT:
- Practical, not maximalist. Speaks from operations, not theory.
- Bullish on AI leverage but skeptical of AI theater.
- Does not posture as a coder. Does not use smug dunking tone.
- Calm confidence, not hype. Direct but not combative.
- Self-deprecation ratio: 1 per 3 serious posts.
- Never pretends certainty without evidence. No fake vulnerability.
- No dunking on small accounts. No medical/legal certainty.

**Anti-voice rules (what Brad NEVER sounds like):**
- Corporate jargon ("synergy," "leverage," "ecosystem play")
- Hype bro ("THIS IS INSANE," "mind-blowing," "game-changer")
- LinkedIn cringe ("I'm humbled to announce," "Agree?")
- AI slop (overly structured, too many bullet points in casual posts)
- Salesy ("DM me to learn more," "Link in bio")

### Golden Corpus (`data/voice_corpus/`)
50-100 curated pieces of real Brad material:
- Voice memo transcripts (highest fidelity)
- Written emails, texts, posts
- Brad's edits to AI-generated drafts (gold signal — captures what he changes and why)
- NOT just best-performing posts (biases toward engagement bait)

Tagged by: platform, tone, topic, format, quality score, "very Brad" vs "acceptable."

### Retrieval-Augmented Voice (RAV)
Before generating any content, Creator/Engager queries the golden corpus by topic + platform:
- "Write a reply about cannabis compliance for X. Here are 4 examples of how Brad handles similar topics."
- Grounds every generation in actual Brad voice, not generic AI

### Platform-Specific Voice Variants
Same person, different room:
- **X:** Concise, sharper, more conversational. Punchy hooks.
- **LinkedIn:** More complete, contextual, less combative. Business implications framing. 800-1200 words for long-form.
- **Threads:** Lighter, casual, lower argumentative density. Personal.

### Voice Scoring Rubric
Every output scored before publish:
- Sounds like Brad (1-5)
- Platform-native (1-5)
- Adds value, not generic (1-5)
- Appropriately confident (1-5)
- Low cringe (1-5)
- Safe/compliant (pass/fail)

Minimum score: 3.5 average across dimensions. Below → regenerate or discard.

### Drift Detection (Analyst runs weekly)
- Compare week's outputs to golden corpus (embedding cosine similarity)
- Flag repeated phrases, rising verbosity, increasing abstraction
- Detect overuse of "AI operator" language or rising hype
- Brad's monthly voice calibration: review 20 random posts, flag drift

### Source Hierarchy (prevents memory contamination)
1. Brad's direct inputs: voice memos, transcripts, explicit edits (HIGHEST)
2. Brad's published canonical posts
3. Approved generated content
4. External inspiration/trends
5. Agent summaries (LOWEST — never use as voice training signal)

Lower tiers never override higher tiers in voice shaping.

---

## Shared Infrastructure

### `lib/events.py` — Event Log + State Store
SQLite (WAL mode). Two concerns: immutable event log + mutable state projections.

```sql
-- Immutable event log
CREATE TABLE events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    agent TEXT NOT NULL,
    event_type TEXT NOT NULL,
    details TEXT,               -- JSON blob
    failure_category TEXT,
    duration_ms INTEGER
);

-- Pending actions (idempotency)
CREATE TABLE pending_actions (
    idempotency_key TEXT PRIMARY KEY,  -- e.g. reply:x:12345:abc123
    agent TEXT NOT NULL,
    action_type TEXT NOT NULL,
    payload TEXT,               -- JSON blob
    status TEXT DEFAULT 'pending',  -- pending, sent, verified, failed
    created_at TEXT NOT NULL,
    completed_at TEXT
);

-- Platform cooldowns (durable, shared across agents)
CREATE TABLE platform_cooldowns (
    platform TEXT PRIMARY KEY,
    cooldown_until TEXT NOT NULL,
    reason TEXT,
    set_by TEXT
);

-- Agent heartbeats (orchestrator monitors)
CREATE TABLE agent_heartbeats (
    agent TEXT PRIMARY KEY,
    last_heartbeat TEXT NOT NULL,
    status TEXT DEFAULT 'healthy'
);

-- Strategy state (Analyst writes, all agents read)
CREATE TABLE strategy_state (
    key TEXT PRIMARY KEY,
    value TEXT,                 -- JSON blob
    version INTEGER DEFAULT 1,
    updated_at TEXT
);

-- Tier targets (Engager reads, manually curated + Scout updates)
CREATE TABLE tier_targets (
    handle TEXT PRIMARY KEY,
    tier INTEGER NOT NULL,      -- 1, 2, or 3
    platform TEXT DEFAULT 'x',
    last_interaction TEXT,
    interaction_count INTEGER DEFAULT 0,
    notes TEXT
);
```

Log **decision-relevant** transitions, not internal chatter:
- "engagement candidate selected", "post verified", "cooldown entered", "strategy v12 activated", "breakout detected", "newsjack drafted"
- NOT "entered function", "considered 47th candidate"

### `lib/signals.py` — Cross-Agent Signal Bus
In-memory deque — **ephemeral nudges, NOT source of truth.** Signals = "hey, look now." SQLite = "this happened, durably."

Each signal includes: `type`, `emitted_at`, `source_agent`, `entity_key`, `priority`, `ttl`, `dedupe_key`.

| Signal | Source | Type | Effect |
|--------|--------|------|--------|
| `HOT_TARGET` | Outbound (radar score > 80) | ephemeral | Orchestrator runs Outbound NOW |
| `TIER1_ACTIVE` | Scout | ephemeral | Outbound prioritizes Tier 1 response |
| `DM_OPPORTUNITY` | Inbound (3-touch threshold) | ephemeral | Queued to Brad's Slack morning briefing |
| `RELATIONSHIP_OVERLOAD` | Inbound (backlog > threshold) | ephemeral | Outbound reduces proactive volume |
| `API_BLOCKED` | Any agent (HTTP 403) | durable-backed | All agents check cooldown table |
| `POST_SENT` | Publisher | ephemeral | Triggers cross-platform relay |
| `STRATEGY_UPDATE` | Analyst (growth audit) | durable-backed | All agents reload from strategy_state table |
| `CONTENT_LOW` | Publisher (backlog < 5) | ephemeral | Triggers Creator replenish |
| `NEWSJACK_READY` | Scout | ephemeral | Orchestrator fast-tracks to Publisher |
| `BREAKOUT_DETECTED` | Analyst (5x baseline) | ephemeral | Orchestrator triggers amplification cascade |
| `VIDEO_READY` | Creator (video pipeline) | ephemeral | Publisher adds to next posting cycle |
| `BRAND_SAFETY_CHANGE` | Policy (state transition) | durable-backed | All agents check new operating mode |
| `VOICE_DRIFT` | Analyst (weekly audit) | ephemeral | Creator reloads voice constitution |

Signal bus includes: coalescing (dedup by key), TTL expiry, backpressure (max queue depth).

Wrapped in `SignalBus` abstraction class — backend swappable later without changing agent code.

### `lib/failure.py` — Failure Taxonomy + Retry
```
RATE_LIMITED      — HTTP 429         → retry 5min backoff, no budget cost
NETWORK_ERROR     — timeout/conn     → retry 2min backoff, no budget cost
AUTH_EXPIRED      — HTTP 401         → immediate escalation, no retry
PLATFORM_COOLDOWN — HTTP 403         → durable cooldown in SQLite, no retry
CONTENT_BLOCKED   — filter flags     → dead letter, needs human edit
DUPLICATE_CONTENT — dedup match      → skip silently
INVALID_TARGET    — deleted tweet    → skip, log
API_ERROR         — HTTP 5xx         → retry 5min backoff, no budget cost
UNKNOWN           — uncaught except  → retry once (budget cost), then dead letter
```
2 retries (3 total attempts). Infra failures don't consume action budget BUT consume time-window circuit breaker (5 infra failures in 10 min → platform degraded state).

### `lib/platforms.py` — Platform Abstraction + Rate Limit Manager
Unified interface for X, Threads, LinkedIn. Each platform module:
- `post(text, **kwargs) -> Result` (supports text, thread, video, QT)
- `verify(post_id) -> bool`
- `get_metrics(post_id) -> dict`
- `get_profile() -> dict`

**Platform autonomy levels (consortium-validated):**
- **X:** Semi-autonomous posting + engagement via API. Most automated platform.
- **LinkedIn:** Playwright browser automation. Brad's real credentials, human-like delays, session persistence. Posting + commenting supported. Higher fragility — built with fallback to manual queue if Playwright breaks.
- **Threads:** Meta Graph API for publishing. Engagement automation only after trust Phase C.

**LinkedIn via Playwright (`lib/platforms/linkedin.py`):**
- Persistent browser session with Brad's credentials (stored securely)
- Human-like delays between actions (5-30s random)
- Session refresh on schedule (not per-action)
- Fallback: if Playwright fails, items queue to Slack for manual paste
- Anti-detection: randomized viewport, natural scroll patterns, varied timing
- Daily action cap: 2 posts, 5 comments (conservative to avoid LinkedIn detection)

**Centralized rate limit manager** (token bucket). All agents must go through this before any API call. Budget priority when scarce:
1. Reactive replies to direct mentions (Inbound Engager)
2. Tier 1 account engagement (Outbound Engager)
3. Newsjack posts (Publisher, urgent)
4. Thread continuation (Inbound Engager)
5. Proactive high-value engagement (Outbound Engager)
6. Scheduled publishing (Publisher)
7. Low-value relays (Publisher)

Engagers preempt Publisher on scarce budget.

Includes Threads API module (Meta Graph API v18+):
- POST `/threads` with `media_type=TEXT` → creation_id
- POST `/threads_publish` with creation_id → thread_id

Platform cooldowns checked from SQLite before every API call (not just signal bus).

### `lib/voice.py` — ElevenLabs Voice Synthesis
Brad's voice clone on ElevenLabs. Used by Creator's video pipeline.
- `synthesize(script: str) -> Path` — generate audio file in Brad's voice
- `get_voice_id() -> str` — configured voice clone ID
- API key from `~/.zsh_env` as `ELEVENLABS_API_KEY`

### `lib/video.py` — Terminal Video Pipeline
Capture + package terminal recordings as video content.
- `capture_terminal(command: str, duration: int) -> Path` — asciinema recording
- `render_video(recording: Path, audio: Path) -> Path` — combine into MP4
- `create_clip(forge_log: str, script: str) -> Path` — end-to-end: log → video
- Dependencies: asciinema, ffmpeg (both available via homebrew)

### `lib/config.py` — Centralized Configuration
Loads from `~/.zsh_env` + `config.yaml`. API keys, schedule intervals, quality thresholds, daily caps. Single source of truth. Strategy weights live in SQLite (updated by Analyst), not config file.

---

## Directory Structure

```
~/Projects/groundswell/
├── orchestrator.py          # Main daemon — scheduler, coordinator, monitor
├── config.yaml              # All tunable parameters
├── agents/
│   ├── __init__.py
│   ├── publisher.py         # Drip posting, verification, cross-platform
│   ├── outbound.py          # ⭐ Growth engine — proactive replies, QTs, strategic follows
│   ├── inbound.py           # ⭐ Relationship keeper — reply monitoring, threading, DM flags
│   ├── analyst.py           # Metrics, followers, growth audit, breakout detection
│   ├── creator.py           # Content factory — text, video, collabs, system mining
│   └── scout.py             # Trend detection, newsjacking, opportunity tracking
├── lib/
│   ├── __init__.py
│   ├── events.py            # SQLite: event log + pending_actions + cooldowns + strategy + tiers
│   ├── signals.py           # SignalBus abstraction (deque backend, swappable)
│   ├── failure.py           # Failure taxonomy + retry budget + circuit breaker
│   ├── policy.py            # ⭐ Policy/Safety shared service — brand safety state machine
│   ├── platforms/            # Platform abstraction layer
│   │   ├── __init__.py      # Unified interface + centralized rate limit manager
│   │   ├── x.py             # X/Twitter API v2
│   │   ├── linkedin.py      # LinkedIn via Playwright browser automation
│   │   └── threads.py       # Threads via Meta Graph API
│   ├── voice/                # Voice system (infrastructure, not afterthought)
│   │   ├── __init__.py      # Voice scoring, RAV retrieval, drift detection
│   │   ├── elevenlabs.py    # ElevenLabs voice synthesis for video
│   │   └── constitution.py  # Voice rules loader, anti-patterns, platform variants
│   ├── video.py             # Terminal recording + video packaging
│   ├── intake.py            # Voice memo pipeline (Whisper → Claude → atomize → queue)
│   ├── atomizer.py          # One moment → 8 platform-native pieces
│   ├── proof_stack.py       # Automated receipt collection + milestone tracking
│   ├── config.py            # Config loader
│   └── content_filter.py    # Safety gate (copied from forge)
├── data/
│   ├── backlog.json         # Content queue (migrated from forge)
│   ├── groundswell.db       # SQLite: events + engagement + followers + state + proof_stack
│   ├── dead_letter.json     # Failed posts needing human review
│   ├── voice_constitution.md # Voice rules document
│   ├── voice_corpus/        # Golden corpus — real Brad material (tagged)
│   ├── videos/              # Generated video content
│   └── growth_audits/       # Weekly audit JSONs
├── legacy/                  # Quarantine zone — shrinking only
│   ├── README.md            # What's here, who owns it, removal targets
│   ├── platform_x.py        # X API functions (from radar.py, post.py)
│   ├── content_pipeline.py  # Backlog/drip functions (from drip.py)
│   └── engagement_rules.py  # Engage logic (from auto_engage.py)
├── tests/
│   ├── test_publisher.py
│   ├── test_outbound.py
│   ├── test_inbound.py
│   ├── test_analyst.py
│   ├── test_creator.py
│   ├── test_scout.py
│   ├── test_policy.py
│   └── test_orchestrator.py
├── requirements.txt
├── CLAUDE.md                # Agent operating instructions
└── com.groundswell.plist    # launchd config
```

**Legacy organized by capability, not old file names.** Each file tagged with: owner agent, source file, side effects, internal retries (to strip), removal target.

---

## Orchestrator Schedule

| Task | Agent | Interval | Jitter | Timeout |
|------|-------|----------|--------|---------|
| drip | Publisher | 30 min | 0-17 min | 120s |
| verify_posts | Publisher | 5 min | 0 | 30s |
| cross_platform | Publisher | after drip | 0 | 120s |
| outbound_engage | Outbound Engager | 1 hr | 0-10 min | 600s |
| quote_tweets | Outbound Engager | 2 hr | 0-15 min | 300s |
| reply_monitor | Inbound Engager | 30 min | 0 | 120s |
| thread_check | Inbound Engager | 1 hr | 0 | 120s |
| trend_scan | Scout | 30 min | 0-5 min | 120s |
| tier1_monitor | Scout | 15 min | 0 | 60s |
| metrics | Analyst | 6 hr | 0-30 min | 300s |
| breakout_check | Analyst | 30 min | 0 | 30s |
| voice_drift | Analyst | daily 11pm | 0 | 120s |
| followers | Analyst | daily 6am | 0 | 60s |
| growth_audit | Analyst | weekly Sun 6am | 0 | 120s |
| replenish | Creator | daily 5am | 0 | 600s |
| hook_rewrite | Creator | daily 4am | 0 | 600s |
| system_mine | Creator | every 4 hr | 0-15 min | 300s |
| video_generate | Creator | daily 3am | 0 | 900s |
| forge_dispatch | Creator | weekly Sun 4am | 0 | 600s |
| policy_state | Policy | 15 min | 0 | 10s |
| health_check | Orchestrator | 15 min | 0 | 5s |

Jitter applied at orchestrator level. Subagents never sleep for jitter. Main loop sleeps until next task due (max 60s).

---

## Growth Strategy (Baked Into Agents)

### Phase 0: The Manual Blitz (THIS WEEK — while Groundswell gets built)
Don't wait for the engine. Start moving NOW.
- **Brad posts the Day 1 manifesto** — "I'm a non-engineer running an 8-figure business with 7 people. The rest of my workforce is AI agents. I'm documenting everything." Pin it.
- **Brad manually comments on 10 Tier 1 posts per day** — AI/tech AND cannabis, split evenly
- **Cannabis LinkedIn offensive starts** — 3 opinionated cannabis operations posts this week
- **Fix the existing autopilot** (timeout already fixed) — keep current drip running
- **Curate BOTH Tier 1 lists** — AI/tech (5-10 handles) AND cannabis (5-10 handles)
- **Set up Threads account** if not already active
- **Get ELEVENLABS_API_KEY into ~/.zsh_env**
- **Research MJBizCon 2027 speaker submission timeline** — know the deadline

### Phase 1: Foundation (Weeks 1-4, March-April 2026, 44 → 500)
- **Groundswell goes live** — 6 agents running, 40+ daily touchpoints
- **Identity:** Name "Cross-Brain Architecture" in definitive thread. Establish "AI Operator" category.
- **Dual-vertical launch:** AI content on X, cannabis operations content on LinkedIn — simultaneously
- **Engager:** 25+ interactions/day, split across AI Tier 1 (X) and cannabis Tier 1 (LinkedIn)
- **Publisher:** Atomized content across X, Threads, LinkedIn (platform-native, not cross-post)
- **Creator:** First terminal videos (ElevenLabs), hook-optimize backlog, first "Operations Autopsy"
- **Creator:** Launch FORGE Dispatch weekly + Commit of the Day daily
- **Scout:** Newsjacking both AI AND cannabis news. First cannabis regulatory newsjack.
- **Commit counter:** Start tracking publicly. "Week 1: 34 commits."
- **Cannabis LinkedIn:** 3-5 opinionated cannabis posts/week. Get Shadd Dale to engage once.
- **Brad (15 min/day):** Morning scan + personal comments on Tier 1 in BOTH verticals

### Phase 2: Credibility Building (Weeks 5-12, May-June 2026, 500 → 3K)
- **Volume scales:** 40-50 touchpoints/day across all platforms
- **Creator:** Viral threads + terminal videos + Carric collabs + "Cannabis AI Playbook" (free)
- **Cannabis speaking:** Land first small cannabis speaking gig (regional event, Aroya event, webinar)
- **Cannabis podcasts:** Guest on 2-3 cannabis industry podcasts as "The AI Operations Guy"
- **Analyst:** Weekly growth audit, breakout detection, separate cannabis engagement tracking
- **Scout:** 2-3 breaking stories/week, cannabis regulatory newsjacks, MSO earnings analysis
- **Engager:** Cannabis Tier 1 relationships deepening — Shadd Dale engaging regularly
- **Commit counter:** "Month 2: 247 commits. Stripe's CEO did 950 all year."
- **Leverage reports:** Monthly "7-person stack" showing agent-handled cannabis operations
- **Target: MJBizDaily mentions AI in cannabis operations, ideally references Brad**
- **Brad:** 2-3 cannabis podcast recordings, 1 speaking clip recorded

### Phase 3: MJBizCon Application (July 2026, 3K → 5K)
- **SUBMIT MJBIZCON SPEAKER APPLICATION**
  - Title: "7 People, 1,800 Commits, Zero Engineers: How AI Agents Run My Cannabis Operations"
  - Include: follower count, podcast clips, speaking clip, Cannabis AI Playbook, Tier 1 endorsements
  - Differentiator: "Live demo on stage — real terminal, real agents, real compliance workflow"
- **Drop the Collison comparison thread** (timed for maximum impact around submission)
- **Analyst:** Moment detection active — amplification cascade on breakout posts
- **Creator:** Video pipeline at velocity (3+/week), No-Touch Days as content
- **Movement:** "AI Operators" gaining traction in both AI and cannabis circles
- **Cannabis Tier 1 warm intros:** Aroya contacts → cultivators → MSO ops leaders

### Phase 4: Momentum (Aug-Dec 2026, 5K → 20K)
- **Whether MJBizCon accepted or not — keep building regardless**
- **Benzinga Cannabis Conference** as backup/warmup speaking gig
- **Creator economy grenade:** "Cardone has 200 people. Gary Vee has 30. I have zero."
- **Newsletter launch** (email = owned audience)
- **Engager:** Tier 1 co-signs materializing — Kim Rivers, Shadd Dale sharing/engaging
- **Creator:** "How my AI agents ran cannabis operations while I was offline for 36 hours"
- **Stack speaking gigs** — each one makes the next easier
- **Build relationships with past MJBizCon speakers** (they influence the committee)
- **YouTube Shorts + TikTok** pipeline from terminal videos
- **Media:** Cannabis press + tech press finding Brad organically
- **Commit counter:** "1,200 commits. Zero engineers. 8-figure cannabis operations."
- **If MJBizCon waitlisted:** request panel slot, sponsor session, host side event. Get IN the building.

### Phase 5: MJBizCon + Advisory (January 2027+)
- **MJBIZCON STAGE** — live terminal demo, AI agents running real compliance workflow while Brad narrates
- Every MSO executive in the room thinking "I need to talk to this guy"
- **"Brad Wood" = synonymous with AI-driven cannabis operations**
- Advisory/COO/CEO inbound from major cannabis players
- Speaking circuit: cannabis conferences AND AI conferences (dual-vertical flywheel)
- Product brand (@aianna) positioned as the platform behind the story
- **The content engine continues autonomously — Brad's 15 min/day never changes**
- The agent army that grew the following IS the proof that the advisory pitch works

---

## Migration from forge-ecosystem

1. `mkdir -p ~/Projects/groundswell/{agents/engager,lib,data/videos,legacy,tests}`
2. `git init ~/Projects/groundswell`
3. Extract reusable functions from `tools/social/` into `legacy/`:
   - `drip.py` → `legacy/content_pipeline.py` (load_backlog, save_backlog, current_slot, remaining_quota, post_item, get_pending, classify_theme, count_posted_today, DAILY_LIMITS, TIME_SLOTS)
   - `radar.py` + `post.py` → `legacy/platform_x.py` (_x_get, OAuth helpers, post functions)
   - `auto_engage.py` → `legacy/engagement_rules.py` (core engage logic, loosened quality gates)
4. Copy `content_filter.py` → `lib/content_filter.py`
5. Copy `engagement_db.py` → basis for `lib/events.py` (expand schema)
6. Copy `backlog.json` → `data/backlog.json`
7. Build new files: orchestrator.py, all agents, all lib modules
8. Create `com.groundswell.plist` launchd config
9. Test: `python3 orchestrator.py --dry-run`
10. Deploy: `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.groundswell.plist`
11. Keep `tools/social/autopilot.py` running until groundswell verified stable (parallel run)

---

## Verification

1. **Unit tests**: Each agent tested in isolation with mock APIs
2. **Dry run**: `python3 orchestrator.py --dry-run` — full cycle, all agents, no posting
3. **Single agent test**: `python3 -m agents.engager --dry-run` — test engagement in isolation
4. **Scout test**: `python3 -m agents.scout --dry-run` — verify trend detection catches known events
5. **Video test**: `python3 -m agents.creator --test-video` — generate one test video with ElevenLabs
6. **Parallel run**: Run groundswell alongside old autopilot for 24-48 hours
7. **Live verification**: Watch logs, confirm posts + cross-post + engagement + video
8. **Failure sim**: Bad API key → confirm classification → retry → escalation
9. **Growth audit**: Run manually, confirm strategy weights propagate to all agents
10. **Newsjack sim**: Feed a fake trending topic → verify Scout catches it → Creator drafts take → Publisher queues

---

## Build Order

### Phase 0: Manual Blitz (THIS WEEK, before any code)
0. Brad posts Day 1 manifesto manually
1. Brad curates Tier 1 list (5-10 handles)
2. Brad starts manual commenting on Tier 1 posts (10/day)
3. Set up ELEVENLABS_API_KEY, THREADS_ACCESS_TOKEN in ~/.zsh_env
4. Fix existing autopilot timeout (already done) — keep drip running

### Phase 1: Core Infrastructure
1. `mkdir -p ~/Projects/groundswell/...` + `git init`
2. **lib/events.py** — full SQLite schema (events, pending_actions, cooldowns, heartbeats, strategy_state, tier_targets, proof_stack)
3. **lib/policy.py** — Brand Safety State Machine (GREEN/YELLOW/RED/BLACK), topic safety, compliance, stale content TTL, human cadence governor, abstention rule
4. **lib/platforms/** — X API module, LinkedIn Playwright module, Threads Graph API module, centralized rate limit manager
5. **lib/voice/** — Voice Constitution loader, golden corpus retrieval (RAV), voice scoring rubric, platform variants, drift detection
6. **lib/signals.py + lib/failure.py + lib/config.py + lib/content_filter.py** — Signal bus, failure taxonomy, config, safety gate
7. **lib/video.py + lib/intake.py + lib/atomizer.py + lib/proof_stack.py** — Video pipeline, voice memos, atomization, receipts
8. **legacy/** — extract functions from forge tools/social/ behind adapters
9. **data/voice_constitution.md + data/voice_corpus/** — Brad writes voice doc, curates 50-100 golden corpus pieces

### Phase 2: Agents (publisher first, engagement last)
10. **orchestrator.py** — scheduler, reconciliation, health monitoring, deadman switch, amplification cascade, trust phase management
11. **agents/publisher.py** — posting (text + thread + video), verification, cross-platform (platform-native)
12. **agents/scout.py** — trend detection + newsjacking (early value)
13. **agents/analyst.py** — metrics, growth audit, breakout detection, voice drift monitoring
14. **agents/creator.py** — content factory: replenish, system mining, video pipeline, FORGE Dispatch, atomization, story arc
15. **agents/outbound.py** — growth engine: proactive replies, QTs, strategic follows, tiered targeting
16. **agents/inbound.py** — relationship keeper: reply monitoring, conversation threading, DM opportunity flagging

### Phase 3: Launch (Trust Phase A — Assisted Autopilot)
17. **Tests + dry run** — each agent in isolation, Policy/Safety validation
18. **Slack bot** — approval UX: daily morning batch, approve/edit/reject buttons, kill switch
19. **Deploy in Trust Phase A** — all posts require Brad approval, 10-15 touchpoints/day
20. **Voice calibration** — first week: Brad reviews every output, refines voice constitution
21. **Parallel run** — alongside old autopilot for 48 hours, then cut over

### Phase 4: Trust Escalation
22. **Trust Phase B** (after zero incidents, ~week 4) — selective autonomy, 20-30 touchpoints/day
23. **Trust Phase C** (after 30-45 days zero incidents) — broad autonomy, 35-50 touchpoints/day
24. **First "No-Touch Day"** — verify system runs 24h without Brad

---

## Key External Dependencies

| Service | Purpose | Auth |
|---------|---------|------|
| X API v2 | Post, engage, metrics, search | OAuth 1.0a (in ~/.zsh_env) |
| Threads API (Meta Graph) | Cross-post text + video | Long-lived token (THREADS_ACCESS_TOKEN) |
| LinkedIn (Playwright) | Posting + commenting via browser automation | Brad's LinkedIn credentials (stored securely) |
| ElevenLabs API | Voice synthesis (Brad's cloned voice) | API key (ELEVENLABS_API_KEY) |
| Claude API | Content drafting, QT takes, hook rewriting, voice scoring | API key (existing) |
| Slack API | Approval UX — daily batch, approve/edit/reject, kill switch | Bot token (SLACK_BOT_TOKEN) |
| HackerNews API | Trend detection (free, no auth) | None |
| RSS feeds | News monitoring | None |
| Playwright | LinkedIn browser automation | Local install (pip) |
| asciinema + ffmpeg | Terminal recording + video packaging | Local install (homebrew) |

## Credentials Brad Needs to Set Up
- `THREADS_ACCESS_TOKEN` — requires Instagram Business Account linked to Facebook Page
- `ELEVENLABS_API_KEY` — already has voice cloned, need API key in ~/.zsh_env
- `SLACK_BOT_TOKEN` — create Slack app for approval workflow (or use existing workspace)
- LinkedIn credentials — for Playwright browser automation (stored in keychain, not env file)
- Tier 1 account list — Brad curates initial 5-10 kingmaker handles (AI/tech + cannabis)
- Voice corpus — Brad curates 50-100 pieces of his best writing/transcripts for golden corpus

---

## Monthly Budget: $500

| Line Item | Monthly | Why |
|---|---|---|
| X Premium | $40 | **Already paying.** Blue check, reply boost, longer posts, edit. Replies surface higher to Tier 1 — this alone is worth more than any promoted tweet. |
| LinkedIn Premium | $60 | InMail credits for warm outreach, profile analytics, who-viewed visibility |
| LinkedIn ads (cannabis) | $200 | Surgical targeting: cannabis ops leaders, 50-500 employee companies, specific states. LinkedIn audience doesn't penalize "Promoted" like X does. |
| ElevenLabs Pro | $22 | 100 min/month voice synthesis — 12-15 terminal videos |
| Claude API | $100 | Content gen, hook rewriting, atomization, system mining, breakout amplification drafts |
| Beehiiv Pro (newsletter) | $42 | "FORGE Dispatch" weekly email — owned audience, not platform-dependent |
| Reserve | $36 | ONLY spent when Analyst detects genuine breakout (5x baseline). Boost proven organic winners on LinkedIn, never cold content. |
| **Total** | **$500** | |

**No X promoted posts.** They show "Promoted," the AI/tech crowd dismisses them, and they actively undermine the "built this with zero people" narrative. X Premium's reply boost does more than $500 of promoted tweets ever would.

**LinkedIn ads are the exception.** Cannabis executives live on LinkedIn, the "Promoted" label is subtle, and targeting by job title + company size + industry is surgical. This is the one platform where paid reach converts to real credibility.

**Newsletter from Day 1.** Social platforms can shadowban, throttle, change algorithms overnight. Email subscribers are the only audience Brad owns. The weekly FORGE Dispatch goes to email first, then social.

---

## Proof Stack Agent (`lib/proof_stack.py`)

Systematic collection of undeniable evidence that compounds over time. Not scattered screenshots — a curated, indexed portfolio that feeds content and speaking applications.

**SQLite table (added to groundswell.db):**
```sql
CREATE TABLE proof_stack (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    category TEXT NOT NULL,      -- milestone, metric, endorsement, media, screenshot, before_after
    title TEXT NOT NULL,         -- "Crossed 1,000 followers" or "Kim Rivers replied"
    detail TEXT,                 -- Full context, numbers, links
    evidence_path TEXT,          -- Path to screenshot/video/file
    tags TEXT,                   -- JSON array: ["cannabis", "tier1", "follower_growth"]
    used_in TEXT,                -- JSON array of content IDs where this proof was referenced
    created_at TEXT NOT NULL
);
```

**Auto-collected by agents:**
- **Analyst:** Follower milestones (100, 250, 500, 1K, 2.5K, 5K, 10K, 20K), engagement rate records, best-performing posts
- **Engager:** Every Tier 1 reply/engagement received, notable conversation threads
- **Publisher:** Post verification confirmations with metrics snapshots
- **Scout:** Media mentions, podcast appearances, conference acceptances

**Manually triggered by Brad:**
- Before/after pairs ("compliance workflow: 4 hours manual → 11 minutes with agents")
- Speaking clips, podcast recordings
- Notable DM conversations (screenshot + context)

**Used by:**
- **Creator:** Pulls proof for "receipt posts," thread evidence, speaking applications
- **Analyst:** Growth audit references cumulative proof timeline
- **Brad:** MJBizCon application, podcast pitches, advisory conversations

**The proof compounds.** At 500 followers the stack is thin. At 5,000 it's a portfolio. At 20,000 it's undeniable. The system builds it automatically so Brad never has to remember to screenshot anything.

---

## Crisis Playbook

### Kill Switch
```bash
# One command stops ALL outbound posting across all platforms
python3 orchestrator.py --kill
```
Sets `platform_cooldowns` for ALL platforms to 24 hours in SQLite. Every agent checks cooldowns before any API write. Immediate halt, no waiting for next cycle.

Resume: `python3 orchestrator.py --resume` clears all cooldowns.

### Severity Levels

**LEVEL 1 — Bad post (wrong tone, factual error)**
- Auto-detected by content_filter.py pre-send OR spotted by Brad post-send
- Action: Delete post within 15 minutes. No apology needed if caught fast. Log to proof_stack as "incident" for internal learning.
- Prevention: Tighten quality gate threshold for that content category

**LEVEL 2 — Bad engagement (AI reply to Tier 1 that's off-base or generic)**
- This is why ALL Tier 1 + Tier 2 engagement requires Brad's review
- If one slips through (system error): Delete reply immediately. Brad sends personal follow-up: "That was my system acting up — here's what I actually think about [topic]." Honesty > cover-up.
- Prevention: Add handle to "manual-only" suppression list permanently

**LEVEL 3 — Platform suspension (automation detection)**
- Immediate: Kill switch. All agents halt.
- Appeal process: X has a formal appeal. Document that Groundswell uses official API, not scraping. Show API credentials.
- Continuity: LinkedIn + Threads + newsletter continue. Cross-platform is insurance.
- Post-mortem: Which behavior triggered detection? Reduce volume, increase jitter, adjust patterns.

**LEVEL 4 — Reputation crisis (viral negative attention)**
- Kill switch immediately
- Brad and ONLY Brad responds. No AI drafts for crisis response.
- 24-hour cooling period before resuming automated content
- Analyst reviews what caused the crisis, adjusts strategy weights permanently

### Tone Drift Detection
Monthly "voice calibration" — Analyst pulls 20 random posts from the month, Brad reviews in 10 minutes:
- Does this sound like me?
- Would I actually say this?
- Any cringe?
Flag drift → Creator adjusts voice prompt. Logged in proof_stack as "calibration."

---

## DM Strategy

**Rule: Groundswell NEVER sends DMs. Ever. DMs are Brad only.**

DMs are where deals close and relationships deepen. One AI-generated DM that reads wrong burns a relationship permanently. The public content engine gets attention; Brad's personal DMs convert to relationships.

### When to DM (Brad's playbook)
- **3-touch rule:** After someone engages with Brad's content 3+ times, they're warm. Brad DMs.
- **Template (adapt, don't copy-paste):** "Hey [name] — noticed your work on [specific thing they posted]. I've been solving a similar problem with AI agents at [context]. Would love to compare notes."
- **After podcast cross-promotion:** Personal DM to the host AND 2-3 notable guests. "Great conversation on [episode]. That point about [X] — we're seeing the same thing at scale."
- **After Tier 1 engagement:** If Kim Rivers or Shadd Dale replies to Brad's public comment, wait 24 hours, then DM with something genuinely useful (article, data point, introduction offer).

### What Groundswell DOES for DMs
- **Engager flags DM opportunities:** When a target hits the 3-touch threshold, emit `DM_OPPORTUNITY` signal. Brad sees it in morning review queue.
- **Context card:** For each DM opportunity, Engager generates a 3-line brief: who they are, what they've engaged on, suggested angle. Brad uses this to craft the DM in 30 seconds instead of 5 minutes.
- **Track DM outcomes:** Brad logs whether the DM got a response (yes/no/meeting). Analyst uses this to refine which engagement patterns lead to successful DM conversions.

---

## Podcast Strategy

**Brad's setup:** Addium media team is arranging cross-promotion — big names on Brad's podcast, Brad on theirs. This is active, not aspirational.

### What Groundswell does for podcasts
- **Scout tracks appearances:** When a new episode drops featuring Brad, Scout detects it (RSS monitoring of podcast feeds where Brad is listed as guest).
- **Creator atomizes each appearance:** One podcast → 5-8 content pieces:
  - 3-4 pull quotes as standalone posts (best soundbites, timestamped)
  - 1 thread summarizing key insights from the conversation
  - 1 "behind the scenes" post about the cross-promotion setup
  - Tag/mention the host and show → drives their audience to Brad
- **Engager responds** to every comment on podcast promotion posts — keep the thread alive
- **Proof stack logs** each appearance with show name, audience size, host name, key topics

### Cross-Promotion Flywheel
Each podcast appearance creates content → content drives followers → followers make Brad a more attractive guest → more podcast invitations. Groundswell's job is to maximize the content yield from every single appearance so the flywheel accelerates.

---

## Platform Algorithm Playbook (Baked Into Publisher + Creator)

### X Algorithm Rules (Publisher enforces)
- **Reply velocity matters:** Post hooks that drive replies, not likes. Questions > statements for engagement rate.
- **First 60 minutes are critical:** Orchestrator schedules posts when Brad's audience is most active (Analyst determines optimal windows). Engager front-loads engagement on Brad's new posts.
- **No external links in tweets.** Links kill reach by 50%+. Put links in reply to self. Publisher auto-moves any URL to a reply.
- **Images + screenshots boost reach 2x.** Publisher appends terminal screenshots to text posts when available.
- **Threads get distributed per-tweet.** Each tweet in a thread gets its own algorithmic chance. Front-load the best hook.
- **Quote tweets > retweets.** QT adds Brad's take and gets full algorithmic distribution. RT just passes through. Engager always QTs, never RTs.

### LinkedIn Algorithm Rules (Publisher enforces)
- **Dwell time is king.** Long-form posts that take 30+ seconds to read get boosted. Creator writes LinkedIn versions at 800-1200 words for cannabis content.
- **No external links in post body.** LinkedIn throttles posts with links. Put link in first comment. Publisher auto-moves.
- **Document carousels get 3-5x reach.** Creator generates PDF carousels for framework posts ("The FORGE Pattern in 8 slides").
- **First hour engagement = everything.** Brad's 10-min midday LinkedIn session should include engaging with his OWN recent post's comments.
- **Post frequency sweet spot: 1-2/day.** More than 2 LinkedIn posts/day cannibalizes your own reach. Publisher caps LinkedIn at 2/day.

### Threads Algorithm Rules (Publisher enforces)
- **Conversation chains get boosted.** Threads rewards multi-turn conversations. Engager prioritizes reply threads on Threads.
- **Early-stage platform = less competition.** Same content that gets 10 impressions on X might get 100 on Threads. Worth the cross-post.
- **No hashtags.** Threads doesn't use them algorithmically. Clean text only.

---

## Brad's Weekly Rhythm

### Daily (30 min total, non-negotiable)

**Morning — 7:00am CT (10 min)**
- Review overnight queue: 2-3 items flagged for approval → approve/reject (5 min)
- Scan Analyst overnight summary: any breakouts? any issues? (2 min)
- Quick DM check: any Tier 1 responses to follow up on (3 min)

**Midday — 12:00pm CT (10 min)**
- Personal LinkedIn engagement: comment on 3-5 cannabis Tier 1 posts (10 min)
- This is relationship building, not content production. Read their posts. Write thoughtful comments. Sound like a cannabis operator, not an AI bro.

**Evening — 8:00pm CT (10 min)**
- Personal X engagement: comment on 3-5 AI/tech Tier 1 posts (10 min)
- Same rules. Read. Think. Add insight. This is the highest-leverage 10 minutes of Brad's day.

### Voice Memos (whenever, ~60 sec each)
- When something interesting happens with FORGE, agents, cross-brain, Aroya work
- Into phone → Whisper transcription → Creator atomizes → Publisher queues
- No schedule. Natural cadence. 1-3 per day when inspiration hits.

### Sunday (30 min)
- Review FORGE Dispatch draft (Creator auto-generated) → approve/edit (10 min)
- Review Analyst weekly growth audit → note any strategic shifts (10 min)
- Review 10 random posts from the week for tone drift (5 min)
- Scan proof_stack for new milestones worth highlighting (5 min)

### Monthly (60 min, first Sunday)
- Full voice calibration: review 20 random posts for drift
- Proof stack portfolio review: what evidence has accumulated?
- LinkedIn ad performance review: adjust targeting if needed
- Newsletter subscriber growth check
- Tier 1 relationship assessment: who's engaging back? Who needs more attention?

**Total weekly time commitment: 4 hours (30 min/day × 7 + 30 min Sunday review)**
**Total monthly addition: 1 hour**
**Total: ~17-18 hours/month for a system producing 1,000+ monthly touchpoints.**

---

## Competitive Landscape (March 2026 Research)

*Updated by Scout agent continuously. Initial research below.*

**The "AI Operator" lane is nearly empty.** This is the window.

### Who's Adjacent (and why Brad wins)

| Name | Following | Positioning | Why Brad Differentiates |
|---|---|---|---|
| **Greg Isenberg** (@gregisenberg) | ~1M+ | "One-person businesses with agent swarms." Predicts $100M cos with zero employees. | Evangelist, not practitioner. Talks about it. Brad does it. |
| **Dan Shipper** (@danshipper) | ~36K | CEO of Every. Actually AI-native (15 people, AI-written code, 7-fig). | Closest comp — but media/SaaS, not physical ops. No regulated industry proof. |
| **Liam Ottley** (@liamottley_) | ~700K YouTube | "AI Automation Agency" model. 300K Skool community. | Teaches building agencies for clients. Not running his own operations with agents. |
| **Allie K. Miller** (@alliekmiller) | 72K X, 2M LinkedIn | #1 "AI Business" voice on LinkedIn. Former Amazon/IBM. | Advisor, not operator. No commits, no receipts, no terminal screenshots. |
| **Ethan Mollick** (@emollick) | ~121K | Wharton professor. "One Useful Thing." Academic authority. | Academic framing, not operator. Brad's counter: "I don't study it. I run it." |
| **Kyle Poyar** (@poyark) | Large Substack | Coined "AI-native operator" in B2B growth context. | Wrote about it once. Framed for SaaS/GTM, not operations. |
| **aioperator.sh** | Small | Course/community using "AI Operators" brand. | Faceless course. No founder identity. No receipts. No physical-world ops. |

### The Gaps Nobody Fills

1. **"AI Operator" as a HUMAN identity** — aioperator.sh is a faceless course, Kyle Poyar wrote about it once. No person owns this term. Brad claims it.
2. **Non-engineer who actually OPERATES** (not advises, teaches, or invests) — Dan Shipper is closest but he's media/SaaS. Nobody is running physical-world operations with AI agents publicly.
3. **Cannabis + AI operations = TOTAL VACUUM.** Zero accounts. Zero content. Zero competition. Not one person publicly positioning at this intersection.
4. **Regulated industry proof** — everyone demos AI on todo apps and chatbots. Running agents in a federally illegal, state-by-state regulated industry with compliance nightmares is 10x more credible.

### Brad's Defensive Moat

Even if someone claims "AI Operator" tomorrow, they can't fake:
- 1,800 commits/year as a non-engineer (public GitHub)
- Cross-brain A2A in production (FORGE ↔ APEX)
- AI agents running in cannabis operations (regulated, physical-world)
- The growth engine itself being built by AI agents (meta-proof)
- Cannabis industry relationships (Aroya insider, Tier 1 connections)

### Threat Watch (Scout monitors continuously)
- Any account claiming "AI Operator" identity
- Dan Shipper expanding into physical-world ops narrative
- Greg Isenberg moving from evangelist to practitioner
- Any cannabis tech founder starting an "AI operations" personal brand
- New entrants get flagged in weekly growth audit

**Counter if someone bigger grabs the term:** "I was running AI agents in production cannabis operations — the hardest regulatory environment in America — while you were writing blog posts about it. Here are 1,800 receipts." [terminal screenshot]

Scout updates this section weekly. The window is open NOW. It won't be forever.
