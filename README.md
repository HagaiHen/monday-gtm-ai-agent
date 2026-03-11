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

## Example Run — Monto

Monto is a B2B fintech that manages accounts receivable workflows. The customer submits: Finance & Banking industry, 18-person team, pain point around losing track of overdue invoices.

**Board**

<img width="2432" height="1486" alt="image" src="https://github.com/user-attachments/assets/38c306f8-97a2-4928-8dd1-0f420786d433" />

**Dashboard**

<img width="2460" height="1088" alt="image" src="https://github.com/user-attachments/assets/8bd058d3-94a1-47f1-a9b6-d4e337173ae8" />

**Email**

<img width="208" height="568" alt="image" src="https://github.com/user-attachments/assets/b110674b-f9e3-4f56-8ce7-cf4af07fc94f" />


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
# AI — Required
OPENAI_API_KEY=               # OpenAI API key

# monday.com — Required
MONDAY_API_TOKEN=             # monday.com API token (from your account settings)
MONDAY_ACCOUNT_SLUG=          # your subdomain, e.g. "myteam" from myteam.monday.com

# Company research — Optional (recommended)
TAVILY_API_KEY=               # Tavily API key — enables richer company context for the Questioner

# LangSmith tracing — Optional
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=            # LangSmith API key
LANGCHAIN_PROJECT=gtm-ai-demo

# Infrastructure (pre-filled for Docker)
REDIS_URL=redis://redis:6379
AI_SERVICE_URL=http://ai-service:8000

# Email (pre-filled for dev with Mailpit)
SMTP_HOST=mailpit
SMTP_PORT=1025
```

---

## Assumptions & Shortcuts

- **Payment:** The email includes a link to `monday.com/pricing` and a Calendly link. A real Stripe checkout would require a monday.com account to exist first — that's a production integration step beyond this prototype's scope.
- **Email:** Dev uses Mailpit (local SMTP mock, UI at `http://localhost:8025`) — no real emails are sent. The email template is fully built with board link, dashboard link, pricing recommendation, and purchase CTA. Swap `SMTP_HOST/PORT` for any real SMTP provider in production.
- **Monday MCP:** Boards are created on my personal monday.com account purely to demonstrate that the end-to-end workflow works. The goal is to showcase the AI's ability to understand a customer's needs and translate them into a real, structured workspace.
- **Session TTL:** Redis sessions expire after 24 hours.
