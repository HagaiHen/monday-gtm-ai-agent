# monday.com GTM AI Agent

An autonomous AI sales agent that replaces the entire monday.com GTM flow — from lead capture to a live, personalized workspace — without any human sales rep involvement.

---

## What It Does

A customer lands on the site, fills in a short form, has a 5-message AI discovery conversation, and within minutes receives an email with a fully built monday.com board and dashboard tailored to their exact use case — plus a pricing recommendation and a link to purchase.

**The full journey, automated:**

| Original Step | What the AI Does |
|---|---|
| Contact | Lead form captures name, company, website, industry, use case, team size |
| Qualification | Questioner Agent conducts a live discovery conversation, extracts pain point, current tools, workflows, success metric |
| Demo | Email delivers the board as a live demo, plus a showcase video highlighting the platform's capabilities |
| Use case setup | Researcher + Builder agents create the board and dashboard in the background, tailored to the customer's use case |
| Close & Payment | Email includes plan recommendation based on team size and a direct purchase CTA |

---

## Architecture

```
Browser (Next.js :3001)
    │  form submit → POST /api/sessions
    │  chat → WebSocket /chat namespace
    ▼
Gateway (NestJS :3000)
    │  stores session in Redis
    │  relays WebSocket messages → POST /chat
    │  subscribes to Redis "email:send" → sends email
    ▼
AI Service (FastAPI :8000)
    │  Questioner Agent  ← live, synchronous
    │  [on done] publishes to Redis "pipeline:start"
    │  pipeline consumer (background) picks it up:
    │      Researcher Agent
    │      Builder pipeline (Structure → Content → Delivery)
    │      [on complete] publishes to Redis "email:send"
    ▼
Monday.com (via MCP)       Redis (:6379)       Mailpit (:8025)
```

---

## Customer Journey

### Phase 1 — Lead Form
The customer fills in: **name, email, company, website, industry, use case, team size** 

On submit, the Gateway creates a Redis session and returns a `session_id`. The frontend connects via WebSocket and the chat begins.

### Phase 2 — Discovery Conversation (Questioner Agent)
The AI plays a solutions consultant. On the first message, it fetches company context (Tavily search preferred, homepage scrape as fallback) and opens with a question referencing a specific detail from the company's website — making it feel like a real discovery call, not a chatbot.

Max 5 exchanges. It uncovers:
- Current tools/process
- Where things break down
- Who is involved
- What success looks like

When enough depth is gathered, it emits a JSON done signal internally and the conversation transitions.

### Phase 3 — Background Pipeline (triggered on done)
When the Questioner finishes, the orchestrator publishes a `pipeline:start` event to Redis with the full payload (summary, history, company context). A background consumer running in the AI service picks it up and runs the pipeline asynchronously. The user sees "Your workspace is being prepared — check your email!" immediately.

### Phase 4 — Email Delivery
The customer receives a branded email containing:
- Link to their live monday.com board
- Link to their dashboard with smart widgets
- Pricing recommendation (Standard / Pro / Enterprise) based on team size
- CTA to purchase or book a call

---

## Orchestrator

**File:** `ai-service/orchestrator.py`

The orchestrator is the central coordinator — it doesn't do any AI work itself, it just wires everything together and manages state in Redis.

**Two responsibilities:**

**1. Handle a chat message (synchronous, called per user message)**
1. Load session from Redis
2. If phase is `done` → return "check your email" immediately
3. Save user message to `history:{session_id}` in Redis
4. On first message only — fetch company context via Tavily (or scrape fallback), cache in `website_context:{session_id}`
5. Call Questioner Agent with message, history, session, website context
6. Save Questioner reply to history
7. If Questioner signals done → update session phase to `building`, publish `pipeline:start` event to Redis
8. Return reply to Gateway

**2. Run the background pipeline (async, triggered by `pipeline:start` event)**
1. Call Researcher Agent → receives `BoardBlueprint`
2. Call Builder pipeline (Structure → Content → Delivery)

**Redis keys it manages:**

| Key | What it stores |
|---|---|
| `session:{id}` | Form data + current phase (`questioning` / `building` / `done`) |
| `history:{id}` | Full conversation transcript |
| `website_context:{id}` | Cached company context (Tavily / scrape) |
| `pipeline:start` channel | Triggers background pipeline |
| `email:send` channel | Triggers Gateway to send email (published by Delivery Agent) |

---

## Agent Deep Dive

### 1. Questioner Agent
**File:** `ai-service/agents/questioner.py` | **Model:** GPT-4o-mini, temp 0.7

**Input:** user message, chat history (Redis), session form data, website context (cached in Redis)

**What it does:** Plays a solutions consultant. Opens with a company-specific question from the website context. Asks one question at a time, max 5 exchanges. Extracts: `pain_point`, `use_case`, `current_tools`, `key_workflows`, `success_metric`.

**Output:** Reply to show the user. When done, emits a JSON summary that triggers the pipeline.

**Error handling:** Regex fallback if the done JSON is malformed. If that fails, conversation continues.

---

### 2. Researcher Agent
**File:** `ai-service/agents/researcher.py` | **Model:** GPT-4o, temp 0.3

**Input:** company/industry/website (session), Questioner summary fields, full conversation history, website context (no re-fetch — passed from orchestrator)

**What it does:** Single structured LLM call. Designs a complete board blueprint tailored to the customer — groups (3–5), columns (5–7, always including Priority + Timeline), items (4–6, company-specific, every field filled).

**Output:** `BoardBlueprint` — validated through a two-pass process: deterministic auto-fix first, then an LLM reflection pass if issues were found.

---

### 3. Builder Pipeline
**File:** `ai-service/agents/builder.py` | Connects to monday.com MCP once, shares tools across 3 sequential sub-agents.

#### 3a. Structure Agent
**Model:** GPT-4o-mini | **Tools:** `create_board`, `create_group`, `create_column`, `get_board_info`, `all_monday_api`

Creates the board skeleton: board → subitems column → groups → columns → confirms with `get_board_info`. Outputs `BoardStructure` (board_id, group_map, column_map) parsed from message history.

#### 3b. Content Agent
**Model:** GPT-4o | **Tools:** `create_item`, `change_item_column_values`, `all_monday_api`, `create_update`

For each item: creates it, sets all column values, creates subitems, posts an update note. Outputs list of created item names.

#### 3c. Delivery Agent
**Model:** GPT-4o-mini | **Tools:** `create_board_dashboard`, `send_summary_email`

Creates a dashboard with 2–3 widgets chosen dynamically based on use case and available columns. Publishes `email:send` to Redis — Gateway picks it up and sends the email. If dashboard fails, email is still sent.

**All sub-agents:** tool errors are logged and skipped (never abort). Retry on rate limit (3 attempts, exponential backoff).

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 14 (TypeScript, App Router) |
| Gateway | NestJS (TypeScript), Socket.io |
| AI Service | Python FastAPI, LangChain, LangGraph |
| LLMs | GPT-4o (Researcher, Content), GPT-4o-mini (Questioner, Structure, Delivery, Dashboard) |
| Board creation | monday.com MCP server (`streamable_http`) |
| Session/history store | Redis |
| Email (dev) | Mailpit (SMTP mock, UI at :8025) |
| Orchestration | Docker Compose |

---

## AI Craftsmanship Highlights

**Company-aware opening:** The Questioner scrapes/searches the customer's company before the first message and is instructed to open with a specific detail from their site — not a generic question. This makes it feel like a real consultant who did their homework.

**Structured extraction:** The Questioner outputs a strict JSON schema when done. The Researcher receives both the parsed summary (explicit fields) and the full conversation transcript — giving the LLM a clean anchor plus full nuance.

**Blueprint validation:** The Researcher output goes through a two-pass validation — deterministic structural fixes first, then an LLM reflection pass if issues remain.

**Execution plans, not free agents:** The Builder sub-agents receive explicit step-by-step instructions in their prompts. This dramatically reduces hallucinations and tool misuse compared to open-ended agent prompts.

**Smart widget selection:** The Delivery Agent doesn't create a fixed set of dashboard widgets — it calls GPT-4o-mini with the board's available column types and the customer's use case, and it picks the 2–3 most relevant widgets. It's instructed to never include both battery and status_pie (they're redundant).

**Context reuse:** Website context fetched for the Questioner is cached in Redis and passed to the Researcher — avoiding duplicate Tavily/scrape calls.

**Consistent pub/sub throughout:** Both async triggers use Redis pub/sub — the pipeline start (`pipeline:start`) and the email delivery (`email:send`). Services are fully decoupled: the AI service never calls the Gateway, and the Gateway never calls the AI service directly. All cross-service communication flows through Redis.

---

## Example Run — Monto

Monto is a B2B fintech that manages accounts receivable workflows. The customer submits: Finance & Banking industry, 18-person team, pain point around losing track of overdue invoices.

The Questioner opens with: *"I can see Monto connects into AP portals like SAP and Coupa — is the bottleneck knowing when an invoice is stuck, or coordinating the follow-up once you know it's overdue?"*

After 4 exchanges, the pipeline builds a **"Monto — AR Collection Pipeline"** board with groups (*New Invoice → Follow-up Needed → Escalated → Collected*), realistic items, and a dashboard with Status Breakdown + Items by Stage widgets.

**Board**
![Monto board](docs/screenshots/board.png)

**Dashboard**
![Monto dashboard](docs/screenshots/dashboard.png)

**Email**
![Summary email](docs/screenshots/email.png)

---

## Setup

### Prerequisites
- Docker + Docker Compose
- OpenAI API key
- monday.com API token
- (Optional) Tavily API key for richer company research

### Run

```bash
cp .env.example .env
# Fill in OPENAI_API_KEY, MONDAY_API_TOKEN, MONDAY_ACCOUNT_SLUG
docker compose up --build
```

| Service | URL |
|---|---|
| Frontend | http://localhost:3001 |
| Gateway | http://localhost:3000 |
| AI Service | http://localhost:8000 |
| Mailpit (email UI) | http://localhost:8025 |

### Environment Variables

```
OPENAI_API_KEY=          # Required
MONDAY_API_TOKEN=        # Required — monday.com API token
MONDAY_ACCOUNT_SLUG=     # Required — your monday subdomain (e.g. myteam)
TAVILY_API_KEY=          # Optional — enriches company research
REDIS_URL=redis://redis:6379
AI_SERVICE_URL=http://ai-service:8000
```

---

## Assumptions & Shortcuts

- **Payment:** The email includes a link to `monday.com/pricing` and a Calendly link. A real Stripe checkout would require a monday.com account to exist first — that's a production integration step beyond this prototype's scope.
- **Email:** Dev uses Mailpit (local SMTP mock, UI at `http://localhost:8025`) — no real emails are sent. The email template is fully built with board link, dashboard link, pricing recommendation, and purchase CTA. Swap `SMTP_HOST/PORT` for any real SMTP provider in production.
- **Monday MCP:** Boards are created on my personal monday.com account purely to demonstrate that the end-to-end workflow works. The goal is to showcase the AI's ability to understand a customer's needs and translate them into a real, structured workspace.
- **Session TTL:** Redis sessions expire after 24 hours.
