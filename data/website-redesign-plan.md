# Website Redesign Plan: dbradwood.com + aianna.ai

## The Problem

dbradwood.com is positioned as "I fix broken customer engines" — a CCO turnaround executive looking for PE-backed companies. That was job-search Brad. The site has great bones (dark terminal aesthetic, sharp edges, Geist Mono, scroll animations, 24 published blog posts) but the identity wrapper is wrong for what Brad is now.

Brad is now **The AI Operator**. The site needs to reflect that overnight.

---

## Part 1: dbradwood.com Redesign

### What STAYS (the bones are perfect)
- Dark-first design (#0a0a0a background)
- Zero rounded corners — sharp, direct
- Coral/orange accent (#f97316) — keeps the warmth
- Geist Sans + Geist Mono fonts
- Scroll-triggered fade-in-up animations
- The entire content/writing/ library (24 posts about AI agents — already on-brand)
- The design token system (CSS variables)
- Next.js 16 + MDX pipeline
- Formspree contact form

### What CHANGES

#### 1. Site Config (`src/lib/site.ts`)

**Current:**
```typescript
description: "CCO for PE-backed companies. I fix broken customer engines — build or turnaround."
```

**New:**
```typescript
description: "AI Operator. Non-engineer running an 8-figure business with 7 people and an army of AI agents. Cannabis is the proof."
```

#### 2. Hero Section (homepage `src/app/page.tsx`)

**Current:**
- Headline: "I fix broken customer engines."
- Subheadline: "CCO for PE-backed companies. Thoma Bravo, Apollo, Aroya. Build it or turn it around."
- CTA: "Let's talk"
- Right side: brad-hero.jpg (headshot)

**New:**

```
Headline: "7 people. 1,800 commits. Zero engineers."
Subheadline: "I'm an AI Operator — a non-engineer who runs an 8-figure business
             with an army of AI agents. This is what agent-first operations looks like."
CTA primary: "Read the manifesto" → links to the Day 1 X thread or a /manifesto page
CTA secondary: "See the agents" → links to Groundswell GitHub repo
Right side: Terminal screenshot or animated terminal showing agent output
            (NOT a headshot — the terminal IS the brand)
```

**Why this works:**
- "7 people. 1,800 commits. Zero engineers." is the hook — specific, surprising, memorable
- The three numbers tell the whole story in 7 words
- "AI Operator" establishes the category
- Terminal visual instead of headshot = Brad's visual signature (competitor research confirms nobody else does this)
- Two CTAs: manifesto (for people who want the story) and GitHub (for builders who want the receipts)

#### 3. Approach Section → "The System" Section

**Current:**
- "Same system. Every problem."
- "Diagnose what's actually wrong... Fix it. Iterate."

**New:**
```
Header: "How it works"

Three columns:

Column 1: "Agents think"
"7 specialized AI agents — each with ≤3 responsibilities.
They post, engage, analyze, create, and scout. Full Opus
reasoning on every decision. No shortcuts."

Column 2: "State survives"
"Agents are ephemeral. They start, think, act, exit. All state
lives in SQLite. Fresh context every cycle. Zero drift. I call
this exit-and-reinvoke."

Column 3: "The system learns"
"7 learning loops decompose every action into learnable features.
What works this week informs next week's strategy. Anti-overfitting
built in from day one."
```

**Why:** This section should sell the architecture to technical people and the concept to non-technical people simultaneously. Each column works as a standalone insight.

#### 4. Scoreboard Section

**Current:** NPS turnaround, 95% GRR, "Impossible" → 2 weeks

**New:**
```
Header: "The receipts"

Metric 1: "$222/mo"
"Total cost of a 7-agent autonomous operation.
$200 Claude Max + $22 ElevenLabs. No API calls.
No per-token costs."

Metric 2: "1,800"
"Commits to production AI infrastructure last year.
By a non-engineer. Claude writes the code.
I architect the systems."

Metric 3: "11,000+"
"Lines of code in Groundswell — the agent army
that runs my entire social presence. Built in
one evening. Open source."
```

**Why:** These are the receipts that nobody in the "AI Operator" lane can match. Specific numbers, not claims. Links to proof (GitHub repo, commit history).

#### 5. Quotes Section → "What the agents did today" (Live Section)

**Current:** Two generic executive testimonials

**New:**
Replace static quotes with a LIVE feed from Groundswell. Embed a simplified version of the newsroom — showing the last 5 agent actions in real-time. This is the ultimate "build in public" flex.

```
Header: "What my agents did today"

[Live feed pulling from Groundswell API or a static JSON that updates daily]

• Publisher posted "Exit-and-reinvoke: why my agents forget everything" — 47 impressions
• Outbound Engager replied to @karpathy thread on context windows — 1.7M imp thread
• Scout detected Virginia cannabis bill trending — newsjack drafted
• Inbound Engager responded to @bellman_ych — first engagement on manifesto
• Analyst: Week 1 growth audit complete — 50 followers, target 100
```

If live isn't feasible immediately, use a daily-updated JSON file that the Analyst writes during the Sunday cascade. The feed renders client-side.

**Fallback:** If this is too complex, keep the quotes section but replace with quotes FROM the build-in-public content:
- "My agents posted 47 pieces of content, engaged with 89 accounts, and grew my following by 340 — while I was offline for 36 hours."
- "I told Claude what I wanted and it figured out the rest."

#### 6. About Section → Full Identity

**Current:** 4 paragraphs about PE-backed turnarounds and Riverbed

**New:**
```
Paragraph 1 — The identity:
"I'm Brad Wood. I run customer operations at a cannabis technology
company — 8-figure business, 7 people. I'm not an engineer. Never
was. But I made 1,800 commits to production AI infrastructure last
year because I learned to architect, and Claude learned to code."

Paragraph 2 — The thesis:
"I believe the future of operations is agent-first. AI agents as
primary operators, humans as the escalation path. Not 'AI-assisted.'
Not 'AI-augmented.' Agent-first. I built a 7-agent system that runs
my entire public presence — posting, engaging, learning, adapting —
for $222 a month."

Paragraph 3 — The proof:
"Cannabis is my proof vertical. The hardest regulatory environment in
America — federally illegal, state-by-state compliance, 72-hour
regulation changes. If AI agents can operate here, they can operate
anywhere. That's not a talking point. That's my daily reality."

Paragraph 4 — The invitation:
"I'm building in public. Every commit, every failure, every receipt.
If you're an operator who wants to see what agent-first looks like
in practice — follow along."
```

#### 7. Navigation Update

**Current:** Work | Writing | Contact

**New:** Writing | Agents | About | Contact

- **Writing** stays (24 posts, all on-brand)
- **Agents** → new page showcasing Groundswell: architecture diagram, link to GitHub, the 7 agents explained. This replaces "Work" which had PE turnaround case studies.
- **About** → the full identity page (currently a placeholder)
- **Contact** → calendar link + social links + form

#### 8. Footer Update

**Current:** Just "© 2026 Brad Wood"

**New:**
```
Left: "Brad Wood · AI Operator"
Center: X (@thebeedubaya) | LinkedIn | GitHub | Newsletter
Right: "Built by a non-engineer with an army of AI agents"
```

#### 9. Contact Section Update

**Current:** Name/Email/Message form only

**New:**
```
Header: "Let's talk"
Subheading: "If you're an operator exploring agent-first operations,
            or a cannabis executive wondering what AI can actually do
            for your business — I'd love to compare notes."

Left column: Calendar embed (Cal.com or Calendly — 15-min advisory call)
Right column: Keep the Formspree form for async

Below form: Social links row
  𝕏 @thebeedubaya
  LinkedIn /in/brad-wood
  GitHub /thebeedubya/groundswell
  Newsletter (Beehiiv link when ready)
```

#### 10. New Page: `/agents` (replaces `/work`)

A dedicated page showcasing Groundswell — the agent army itself.

```
Header: "The Agent Army"
Subheading: "7 AI agents running my entire social presence.
            Open source. $222/month. Here's how it works."

Section 1: Architecture diagram
  The run.sh → orchestrator → agent spawn diagram from the README

Section 2: The 7 agents (cards)
  Each agent gets a card: name, emoji, 1-line description, what it owns
  Publisher 📰 | Outbound 📤 | Inbound 📥 | Analyst 📊 | Creator ✍️ | Scout 🔍 | Orchestrator 🎯

Section 3: The learning engine
  Brief explanation of the 7 loops + anti-overfitting

Section 4: GitHub link
  "See the code" → https://github.com/thebeedubya/groundswell

Section 5: Live stats (optional)
  Pull from Groundswell API: posts today, followers, backlog depth
```

#### 11. Meta/SEO Updates

- OG image: generate a new one with the terminal aesthetic + "AI Operator" text
- Meta description: update to match new positioning
- robots.ts: ensure /agents route is indexed
- sitemap.ts: add /agents route

---

## Part 2: aianna.ai Updates

The aianna-landing site on kush is already well-built. Key elements:

**Current state (on kush at ~/Projects/aianna-landing/):**
- Hero: "Your AI wakes up knowing you."
- Features: Autonomous Memory, Emotional Intelligence, Compound Intelligence
- HowItWorks: Install → Converse → Your AI Remembers
- Pricing: Solo (free/OSS), Teams ($29/mo), Platform (custom)
- Stack: Next.js 14, React 18, Tailwind 3, Framer Motion

**What needs updating:**

1. **Domain alignment** — The landing references `aianna.dev` in some places but the product domain is `aianna.ai`. Standardize on aianna.ai.

2. **Connect to Brad's brand** — Add a "Built by Brad Wood" section or footer link to dbradwood.com. The products reinforce each other: Groundswell proves Brad's agent thesis, Aianna is the memory layer that makes it possible.

3. **Dashboard showcase** — The neural dashboard mockup (`aianna-dashboard.html` in forge-ecosystem) should be embedded or screenshotted on the landing page. It's visually stunning and demonstrates what "autonomous memory" actually looks like.

4. **Carric partnership** — The crystal document mentions 50:50 equity with Carric. Make sure the landing page reflects both founders if that's the direction.

5. **Waitlist/early access** — If the product isn't ready for general use, the CTA should be "Join the waitlist" not "Get Started."

6. **Technical differentiation** — The crystal document nails it: "The brain is the thing." Competitors (Mem0, Letta, Zep) build developer infrastructure. Aianna builds the end-user product AND captures emotional state. This should be front and center.

**Recommended changes:**

```
Hero tagline: Keep "Your AI wakes up knowing you." (it's perfect)
Add subline: "Built by the team behind FORGE — 14,000+ memories,
             400 sessions, production for 10 weeks."

Features: Keep all three, add a 4th:
  "Cross-Brain Intelligence" — Two AIs sharing memory across
  organizations via A2A protocol. Your agent knows what their
  agent knows — with consent.

Pricing: Validate tiers with Carric. $29/mo Teams tier is
the wedge for revenue.

Footer: "Built by Brad Wood & Carric Dooley"
        Link to dbradwood.com and APEX
```

---

## Part 3: Implementation Priority

### Phase 1 (Sunday morning — 2 hours)
1. Update `site.ts` description
2. Rewrite hero section (headline, subheadline, CTAs)
3. Rewrite about section (4 new paragraphs)
4. Update navigation (Writing | Agents | About | Contact)
5. Update footer with social links
6. Update contact section with social links

### Phase 2 (Sunday afternoon — 2 hours)
7. Rewrite scoreboard with agent army metrics
8. Replace approach section with "How it works" 3-column
9. Create `/agents` page
10. Update meta/SEO/OG

### Phase 3 (Monday — 1 hour)
11. Replace quotes section with live agent feed or updated quotes
12. Generate new OG image
13. Deploy to Vercel

### Phase 4 (When ready)
14. aianna.ai updates (coordinate with Carric)
15. Calendar integration (Cal.com or Calendly)
16. Newsletter setup (Beehiiv)

---

## Design Decisions Informed by Competitor Research

| Decision | Rationale | Source |
|----------|-----------|--------|
| Terminal visual instead of headshot | Nobody else does this. Visual signature. | All competitors use headshots — differentiate. |
| Specific numbers in hero (7, 1800, 0) | Allie K. Miller uses "2 million followers, 200+ talks" — specificity wins | Allie K. Miller pattern |
| Two CTAs (manifesto + GitHub) | Dan Shipper uses soft CTA + blog archive. Brad needs both story and proof paths. | Dan Shipper + Ethan Mollick patterns |
| "Receipts" over "scoreboard" | Brad's brand is receipts, not claims. This language matches his X voice. | Brad's own voice constitution |
| Live agent feed on homepage | Nobody else shows their AI working in real-time. This is the meta-proof. | Novel — no competitor does this |
| /agents page replacing /work | The agent army IS the work. PE turnaround case studies don't serve the new identity. | Strategic pivot |
| Newsletter CTA eventual | Ethan Mollick's 414K subscribers prove newsletter is the moat. | Ethan Mollick pattern |
| Cannabis as proof, not ceiling | Hormozi model: gyms are his proof, nobody calls him "the gym guy." | PLAN.md strategy, confirmed by Hormozi |

---

## Copy That's Ready to Ship

### Hero headline options (ranked):
1. **"7 people. 1,800 commits. Zero engineers."** ← strongest, most surprising
2. "I run an 8-figure business with AI agents."
3. "The non-engineer who built an agent army."
4. "AI Operator."

### Hero subheadline:
"I'm a non-engineer running an 8-figure business with 7 people and an army of AI agents. Cannabis is the proof vertical. This is what agent-first operations looks like."

### Meta description:
"Brad Wood — AI Operator. Non-engineer. 1,800 commits/year. Running an 8-figure cannabis tech business with 7 people and an army of AI agents. Building in public."

### OG title:
"Brad Wood · AI Operator"

---

## What NOT to Change

- **Don't touch the blog posts.** They're already perfectly on-brand (AI agents, systems, architecture).
- **Don't change the design system.** Dark mode, coral accent, sharp edges, Geist fonts — all perfect for the terminal aesthetic.
- **Don't remove the PE experience entirely.** It goes in the about page as context: "I've operated under Thoma Bravo and Apollo. I know what boards need. Now I build with agents."
- **Don't add a newsletter yet.** Get the site live first, newsletter is Phase 4.
- **Don't add rounded corners.** The sharp edges ARE the brand.
