import json
import logging
import redis.asyncio as redis
from agents.questioner import QuestionerAgent
from agents.researcher import run_researcher, _scrape_website, _tavily_search
from agents.builder import run_builder_agent

logger = logging.getLogger(__name__)

questioner = QuestionerAgent()


async def get_session(redis_client: redis.Redis, session_id: str) -> dict | None:
    data = await redis_client.get(f"session:{session_id}")
    return json.loads(data) if data else None


async def update_session(redis_client: redis.Redis, session_id: str, updates: dict) -> None:
    session = await get_session(redis_client, session_id)
    if not session:
        return
    session.update(updates)
    await redis_client.set(f"session:{session_id}", json.dumps(session), ex=86400)


async def get_website_context(redis_client: redis.Redis, session_id: str) -> str:
    data = await redis_client.get(f"website_context:{session_id}")
    return data if data else ""


async def set_website_context(redis_client: redis.Redis, session_id: str, text: str) -> None:
    await redis_client.set(f"website_context:{session_id}", text, ex=86400)


async def get_history(redis_client: redis.Redis, session_id: str) -> list[dict]:
    data = await redis_client.get(f"history:{session_id}")
    return json.loads(data) if data else []


async def append_history(
    redis_client: redis.Redis,
    session_id: str,
    role: str,
    content: str,
) -> None:
    history = await get_history(redis_client, session_id)
    history.append({"role": role, "content": content})
    await redis_client.set(f"history:{session_id}", json.dumps(history), ex=86400)


async def research_and_build(
    name: str,
    email: str,
    company: str,
    website: str,
    industry: str,
    summary: dict,
    team_size: int = 0,
    history: list[dict] | None = None,
    website_context: str = "",
) -> None:
    """Background task: Research → Builder pipeline."""
    pain_point = summary.get("pain_point", "")
    use_case = summary.get("use_case", "")

    print(f"\n{'='*60}")
    print(f"[Pipeline] Starting for {name} <{email}> @ {company}")
    print(f"[Pipeline] Pain point:     {pain_point}")
    print(f"[Pipeline] Use case:       {use_case}")
    print(f"[Pipeline] Team size:      {team_size}")
    print(f"[Pipeline] Current tools:  {summary.get('current_tools', 'unknown')}")
    print(f"[Pipeline] Key workflows:  {summary.get('key_workflows', [])}")
    print(f"[Pipeline] Success metric: {summary.get('success_metric', 'unknown')}")
    print(f"{'='*60}")

    print("\n[Pipeline] Step 1/2 — Research Agent")
    blueprint = await run_researcher(
        company=company,
        website=website,
        industry=industry,
        pain_point=pain_point,
        use_case=use_case,
        current_tools=summary.get("current_tools", ""),
        key_workflows=summary.get("key_workflows", []),
        success_metric=summary.get("success_metric", ""),
        history=history or [],
        website_context=website_context,
    )

    summary_with_size = {**summary, "team_size": team_size}
    print("\n[Pipeline] Step 2/2 — Builder Agent")
    await run_builder_agent(
        name=name,
        email=email,
        company=company,
        summary=summary_with_size,
        blueprint=blueprint,
        website=website,
        industry=industry,
    )
    print(f"\n[Pipeline] COMPLETE for {email}")


async def handle_chat(
    redis_client: redis.Redis,
    session_id: str,
    message: str,
) -> dict:
    session = await get_session(redis_client, session_id)
    if not session:
        return {"reply": "Session not found.", "phase": "error"}

    if session.get("phase") == "done":
        return {
            "reply": "Your workspace is being prepared. Check your email!",
            "phase": "done",
        }

    await append_history(redis_client, session_id, "user", message)
    history = await get_history(redis_client, session_id)
    prior_history = history[:-1]

    # On first message — fetch company context for the Questioner (Tavily preferred, scraping as fallback)
    website_context = await get_website_context(redis_client, session_id)
    if not website_context and len(prior_history) == 0:
        company = session.get("company", "")
        industry = session.get("industry", "")
        website = session.get("website", "")
        if company:
            print(f"[Orchestrator] Fetching company context for Questioner ({company})...")
            website_context = await _tavily_search(company, industry)
            if not website_context and website:
                print(f"[Orchestrator] Tavily unavailable — falling back to scraping {website}")
                website_context = await _scrape_website(website)
            if website_context:
                await set_website_context(redis_client, session_id, website_context)
                print(f"[Orchestrator] Cached {len(website_context)} chars of company context")

    result = await questioner.invoke(message, prior_history, session, website_context)

    await append_history(redis_client, session_id, "assistant", result["reply"])

    if result["done"]:
        await update_session(redis_client, session_id, {"phase": "building"})
        full_history = await get_history(redis_client, session_id)

        await redis_client.publish("pipeline:start", json.dumps({
            "name": session["name"],
            "email": session["email"],
            "company": session["company"],
            "website": session.get("website", ""),
            "industry": session.get("industry", ""),
            "summary": result["summary"],
            "team_size": int(session.get("team_size", 0)),
            "history": full_history,
            "website_context": website_context,
        }))

        return {"reply": result["reply"], "phase": "done"}

    return {"reply": result["reply"], "phase": "questioning"}
