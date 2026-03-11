"""
Mock run for montopay.com — bypasses the form and chat, goes straight to Research → Builder.
Run inside the container:
  docker-compose exec ai-agent python mock_run.py
"""
import asyncio
import os
from dotenv import load_dotenv

import logging
logging.getLogger("mcp.client.streamable_http").setLevel(logging.ERROR)

load_dotenv()

from agents.researcher import run_researcher
from agents.builder import run_builder_agent

MOCK = {
    "name": "Hagai Hen",
    "email": "hagaihen7@gmail.com",
    "company": "MontoPay",
    "website": "https://montopay.com",
    "industry": "Finance & Banking",
    "pain_point": "Our sales and onboarding teams work in silos — deals close but merchant onboarding gets lost in email threads with no visibility into status or blockers.",
    "use_case": "Merchant onboarding pipeline tracking",
    "team_size": 12,
}


async def main():
    print("\n" + "=" * 60)
    print(f"  MOCK RUN — {MOCK['company']}")
    print("=" * 60)

    summary = {
        "pain_point": MOCK["pain_point"],
        "use_case": MOCK["use_case"],
        "team_size": MOCK["team_size"],
        "current_tools": "Email threads and shared Google Sheets",
        "key_workflows": ["Merchant onboarding", "KYC document collection", "Integration setup"],
        "success_metric": "Every merchant has a clear owner and status visible to the whole team",
    }

    print("\n[Mock] Step 1/2 — Research Agent")
    blueprint = await run_researcher(
        company=MOCK["company"],
        website=MOCK["website"],
        industry=MOCK["industry"],
        pain_point=MOCK["pain_point"],
        use_case=MOCK["use_case"],
    )

    print("\n[Mock] Step 2/2 — Builder Agent")
    await run_builder_agent(
        name=MOCK["name"],
        email=MOCK["email"],
        company=MOCK["company"],
        summary=summary,
        blueprint=blueprint,
        website=MOCK["website"],
        industry=MOCK["industry"],
    )

    print("\n[Mock] Done! Check Mailpit at http://localhost:8025")


if __name__ == "__main__":
    asyncio.run(main())
