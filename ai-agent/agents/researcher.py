import asyncio
import logging
import os
from datetime import date

import httpx
from bs4 import BeautifulSoup
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field, model_validator
from typing import Literal

logger = logging.getLogger(__name__)

MAX_PAGE_CHARS = 8_000   # homepage text cap


# ── Blueprint models ──────────────────────────────────────────────────────────

class ColumnValue(BaseModel):
    title: str = Field(description="Exact column title (must match one of the board's column titles)")
    value: str = Field(description="Realistic value for this column")


class BoardItemBlueprint(BaseModel):
    name: str = Field(description="Item name")
    group: str = Field(description="Which group this item belongs to (must match a group name)")
    status: Literal["Working on it", "Done", "Stuck"]
    priority: Literal["High", "Medium", "Low"]
    timeline_start: str = Field(description="Timeline start date in YYYY-MM-DD format (realistic relative to today)")
    timeline_end: str = Field(description="Timeline end date in YYYY-MM-DD format (must be after timeline_start)")
    column_values: list[ColumnValue] = Field(
        description=(
            "Values for all columns beyond status, priority, and timeline. "
            "Include one entry per remaining column using the EXACT column title. "
            "Example: [{\"title\": \"Contact Email\", \"value\": \"john@acme.com\"}, "
            "{\"title\": \"Notes\", \"value\": \"KYC docs received\"}]. "
            "Must not be empty — fill every column."
        )
    )
    subitems: list[str] = Field(description="2-3 realistic subtask names for this item")
    update_note: str = Field(
        description="A detailed, realistic comment to post on this item — include next steps, blockers, or context"
    )


class BoardGroup(BaseModel):
    name: str = Field(description="Group name representing a workflow phase or category")


class BoardColumn(BaseModel):
    title: str = Field(description="Column display name")
    column_type: str = Field(
        description=(
            "Monday.com column type. Must be one of: "
            "status, text, numbers, date, timeline, long_text, email, phone, link. "
            "Do NOT use 'people' — assignees cannot be set programmatically. "
            "Use 'status' for Priority columns too (not dropdown) — dropdown labels are empty by default. "
            "Use 'timeline' for start/end date ranges (project phases, campaign windows, deal timelines)."
        )
    )


class BoardBlueprint(BaseModel):
    """Full board spec produced by the Research Agent."""
    company_summary: str = Field(description="1-2 sentence summary of what the company does")
    products_services: list[str] = Field(description="Key products or services")
    key_workflows: list[str] = Field(description="Main workflows relevant to their pain point")
    board_name: str = Field(description="Monday.com board name")
    groups: list[BoardGroup] = Field(description="3-5 workflow-phase groups (e.g. pipeline stages)")
    columns: list[BoardColumn] = Field(description="5-7 meaningful columns for this use case")
    items: list[BoardItemBlueprint] = Field(
        description="4-6 realistic items spread across groups — fewer items but every field must be filled completely"
    )

    @model_validator(mode="after")
    def force_priority_to_text(self) -> "BoardBlueprint":
        """Ensure the Priority column is always text type regardless of what the LLM chose."""
        for col in self.columns:
            if col.title.lower() == "priority":
                col.column_type = "text"
        return self


# ── Blueprint validation ──────────────────────────────────────────────────────

VALID_COLUMN_TYPES = {
    "status", "text", "numbers", "date", "timeline",
    "long_text", "email", "phone", "link",
}


def _auto_fix(blueprint: BoardBlueprint) -> tuple[BoardBlueprint, list[str]]:
    """Deterministic structural fixes. Returns (fixed_blueprint, issues_found)."""
    issues: list[str] = []
    group_names = {g.name for g in blueprint.groups}

    # 1. Fix items that reference a non-existent group
    for item in blueprint.items:
        if item.group not in group_names:
            issues.append(
                f"Item '{item.name}' references non-existent group '{item.group}' → reassigned to '{blueprint.groups[0].name}'"
            )
            item.group = blueprint.groups[0].name

    # 2. Remove duplicate column titles (keep first occurrence)
    seen: set[str] = set()
    deduped = []
    for col in blueprint.columns:
        key = col.title.lower()
        if key not in seen:
            seen.add(key)
            deduped.append(col)
        else:
            issues.append(f"Duplicate column '{col.title}' removed")
    blueprint.columns = deduped

    # 3. Remove timeline column if no items have timeline dates
    if any(c.column_type == "timeline" for c in blueprint.columns):
        if not any(item.timeline_start and item.timeline_end for item in blueprint.items):
            issues.append("Timeline column exists but no items have timeline dates → column removed")
            blueprint.columns = [c for c in blueprint.columns if c.column_type != "timeline"]

    # 4. Remove columns with invalid types
    for col in blueprint.columns:
        if col.column_type not in VALID_COLUMN_TYPES:
            issues.append(f"Column '{col.title}' has invalid type '{col.column_type}' → removed")
    blueprint.columns = [c for c in blueprint.columns if c.column_type in VALID_COLUMN_TYPES]

    return blueprint, issues


async def validate_blueprint(blueprint: BoardBlueprint, llm: ChatOpenAI) -> BoardBlueprint:
    """
    Validate and fix a blueprint:
    1. Auto-fix structural issues deterministically
    2. If any issues were found (or the auto-fix crashed), ask the LLM to do a smarter correction pass
    """
    try:
        blueprint, issues = _auto_fix(blueprint)
    except Exception as e:
        issues = [f"Validator crashed: {e}"]
        print(f"[Validator] WARNING: auto-fix failed — {e}")

    if not issues:
        print(f"[Validator] OK — {len(blueprint.groups)} groups, {len(blueprint.columns)} columns, {len(blueprint.items)} items")
        return blueprint

    print(f"[Validator] Found {len(issues)} issue(s) — asking LLM to reflect and fix")
    for issue in issues:
        print(f"[Validator]   • {issue}")

    try:
        fixed: BoardBlueprint = await llm.with_structured_output(
            BoardBlueprint, method="function_calling"
        ).ainvoke([
            SystemMessage(
                "You are a Monday.com board blueprint validator. "
                "You will receive a partially auto-fixed blueprint and a list of issues that were found. "
                "Return a fully corrected blueprint. "
                "For missing timeline dates: add realistic dates rather than removing the column. "
                "For wrong group names: pick the most appropriate existing group for each item."
            ),
            HumanMessage(
                f"Blueprint (partially auto-fixed):\n{blueprint.model_dump_json(indent=2)}\n\n"
                f"Issues found and auto-fixed (verify these are correctly resolved):\n"
                + "\n".join(f"- {i}" for i in issues)
            ),
        ])
        print(f"[Validator] LLM reflection done — {len(fixed.groups)} groups, {len(fixed.columns)} columns, {len(fixed.items)} items")
        return fixed
    except Exception as e:
        print(f"[Validator] WARNING: LLM reflection failed ({e}) — using auto-fixed blueprint")
        return blueprint


# ── Prompts ───────────────────────────────────────────────────────────────────

RESEARCHER_SYSTEM_PROMPT = """You are a Monday.com solutions architect specializing in workflow design.
You are given scraped content from a company's website plus their pain point and use case.

Produce a detailed Monday.com board blueprint that would genuinely help this company:

1. GROUPS — model their real pipeline stages or workflow phases (3-5 groups)
2. COLUMNS — pick 5-7 column types that match real data they'd track. Always include:
   - A "Status" column of type "status" — for item progress tracking
   - A "Priority" column of type "text"
   - A "Timeline" column of type "timeline" — shows start/end dates as a visual bar
   Other columns: date, numbers, long_text, email, phone, link, text.
   Do NOT use 'people' — assignees cannot be set programmatically.
3. ITEMS — create 4-6 realistic items using actual names/products/customers from the website.
   Fewer items, but every field must be filled:
   - status and priority matching the item's current state
   - timeline_start and timeline_end: realistic dates relative to today (provided in the prompt)
   - column_values: REQUIRED — fill EVERY column that is not status, priority, or timeline.
     The key must be the EXACT column title. Example:
       If columns include "Contact Email", "Notes", "Portal Integration":
         column_values = {
           "Contact Email": "john.smith@acmecorp.com",
           "Notes": "KYC documents received, awaiting compliance sign-off",
           "Portal Integration": "SAP Ariba"
         }
     Use realistic, company-specific values. Do NOT leave column_values empty.
   - 2-3 concrete subtask names (subitems) representing real tasks to complete this item
4. UPDATE NOTES — write a realistic comment for each item (e.g. "KYC documents received, waiting for compliance sign-off")

Make it feel like a real live board, not a template. Use company-specific language.
"""


# ── Scraper ───────────────────────────────────────────────────────────────────

async def _scrape_website(url: str) -> str:
    """Scrape homepage and return cleaned text."""
    if not url:
        return ""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        async with httpx.AsyncClient(
            timeout=15.0,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; GTM-Research-Bot/1.0)"},
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
    except Exception as e:
        print(f"[Researcher] Failed to fetch {url}: {e}")
        return ""

    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "noscript", "iframe"]):
        tag.decompose()
    text = " ".join(soup.get_text(separator=" ", strip=True).split())[:MAX_PAGE_CHARS]
    print(f"[Researcher] Scraped {len(text)} chars from {url}")
    return text


# ── Tavily search (optional) ──────────────────────────────────────────────────

async def _tavily_search(company: str, industry: str) -> str:
    api_key = os.getenv("TAVILY_API_KEY", "")
    if not api_key:
        return ""

    try:
        from tavily import TavilyClient  # type: ignore
        query = f"{company} {industry} product features customers use cases"
        client = TavilyClient(api_key=api_key)
        # TavilyClient.search is sync — run in executor to avoid blocking the event loop
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None, lambda: client.search(query, max_results=5)
        )
        snippets: list[str] = []
        for r in response.get("results", []):
            title = r.get("title", "")
            content = r.get("content", "")
            snippets.append(f"**{title}**\n{content}")
        combined = "\n\n".join(snippets)[:6_000]
        print(f"[Researcher] Tavily: {len(response.get('results', []))} results ({len(combined)} chars)")
        return combined
    except Exception as e:
        print(f"[Researcher] Tavily error: {e}")
        return ""


# ── Main ──────────────────────────────────────────────────────────────────────

async def run_researcher(
    company: str,
    website: str,
    industry: str,
    pain_point: str = "",
    use_case: str = "",
    current_tools: str = "",
    key_workflows: list[str] | None = None,
    success_metric: str = "",
    history: list[dict] | None = None,
    website_context: str = "",
) -> BoardBlueprint:
    print(f"\n[Researcher] START — {company} ({website or 'no website'})")

    if website_context:
        print(f"[Researcher] Using cached website context ({len(website_context)} chars) — skipping re-fetch")
        website_section = f"--- Website ---\n{website_context}\n---"
        search_section = ""
    else:
        # Run website scraping and Tavily search in parallel
        website_text, search_text = await asyncio.gather(
            _scrape_website(website),
            _tavily_search(company, industry),
        )

        if website_text:
            website_section = f"--- Website ---\n{website_text}\n---"
        else:
            print("[Researcher] No website content — using form data only")
            website_section = "(No website content — use company name and industry context only)"

        search_section = f"--- Web search results ---\n{search_text}\n---" if search_text else ""

    tools_line = f"Current tools: {current_tools}" if current_tools else ""
    workflows_line = f"Key workflows: {', '.join(key_workflows)}" if key_workflows else ""
    metric_line = f"Success metric: {success_metric}" if success_metric else ""
    extra = "\n".join(filter(None, [tools_line, workflows_line, metric_line]))

    transcript_section = ""
    if history:
        lines = []
        for msg in history:
            role = "Customer" if msg["role"] == "user" else "Consultant"
            lines.append(f"{role}: {msg['content']}")
        transcript_section = "--- Discovery conversation ---\n" + "\n".join(lines) + "\n---"

    context_parts = [website_section]
    if search_section:
        context_parts.append(search_section)
    if transcript_section:
        context_parts.append(transcript_section)

    prompt = f"""Today's date: {date.today().isoformat()}
Company: {company}
Industry: {industry}
Pain point: {pain_point}
Use case: {use_case}
{extra}

{chr(10).join(context_parts)}

Design a complete Monday.com board blueprint for this company.
"""

    print("[Researcher] Calling GPT-4o for board blueprint...")
    llm = ChatOpenAI(model="gpt-4o", temperature=0.3)
    structured_llm = llm.with_structured_output(BoardBlueprint, method="function_calling")

    result: BoardBlueprint = await structured_llm.ainvoke([
        SystemMessage(content=RESEARCHER_SYSTEM_PROMPT),
        HumanMessage(content=prompt),
    ])

    print(f"[Researcher] DONE — board='{result.board_name}'")
    print(f"[Researcher]   groups:  {[g.name for g in result.groups]}")
    print(f"[Researcher]   columns: {[c.title for c in result.columns]}")
    print(f"[Researcher]   items:   {[i.name for i in result.items]}")

    result = await validate_blueprint(result, llm)
    return result
