import os
import logging
from langchain_mcp_adapters.client import MultiServerMCPClient
from .researcher import BoardBlueprint
from .structure_agent import run_structure_agent
from .content_agent import run_content_agent
from .delivery_agent import run_delivery_agent

logger = logging.getLogger(__name__)

MONDAY_API_TOKEN = os.getenv("MONDAY_API_TOKEN", "")


def _print_blueprint(blueprint: BoardBlueprint) -> None:
    print("\n=== Research Blueprint ===")
    print(f"Board:    {blueprint.board_name}")
    print(f"Summary:  {blueprint.company_summary}")
    print(f"Groups:   {[g.name for g in blueprint.groups]}")
    print(f"Columns:  {[f'{c.title} ({c.column_type})' for c in blueprint.columns]}")
    print("Items:")
    for item in blueprint.items:
        print(f"  [{item.group}] {item.name} — {item.status} ({item.priority})")
        for sub in item.subitems:
            print(f"    · {sub}")
    print("=" * 26 + "\n")


async def run_builder_agent(
    name: str,
    email: str,
    company: str,
    summary: dict,
    blueprint: BoardBlueprint,
    website: str = "",
    industry: str = "",
) -> None:
    _print_blueprint(blueprint)

    try:
        print("[Builder] Connecting to Monday MCP...")
        mcp_client = MultiServerMCPClient(
            {
                "monday": {
                    "transport": "streamable_http",
                    "url": "https://mcp.monday.com/mcp",
                    "headers": {"Authorization": f"Bearer {MONDAY_API_TOKEN}"},
                }
            }
        )
        all_monday_tools = await mcp_client.get_tools()
        print(f"[Builder] {len(all_monday_tools)} Monday MCP tools available")
    except Exception as e:
        print(f"[Builder] Failed to connect to Monday MCP: {e}")
        logger.error(f"MCP connection failed for {email}: {e}", exc_info=True)
        return

    # Agent 1 — Board structure (board + groups + columns)
    print("\n[Builder] Stage 1/3 — Structure Agent")
    structure = await run_structure_agent(blueprint, all_monday_tools)
    if not structure:
        print("[Builder] Aborting — board structure was not created")
        return

    # Agent 2 — Content (items + column values + subitems + updates)
    print("\n[Builder] Stage 2/3 — Content Agent")
    created_items = await run_content_agent(blueprint, structure, all_monday_tools)

    # Agent 3 — Delivery (dashboard + email)
    print("\n[Builder] Stage 3/3 — Delivery Agent")
    await run_delivery_agent(
        name=name,
        email=email,
        company=company,
        summary=summary,
        board_name=blueprint.board_name,
        company_summary=blueprint.company_summary,
        structure=structure,
        created_items=created_items or [i.name for i in blueprint.items],
        monday_tools=all_monday_tools,
    )

    print(f"\n[Builder] COMPLETE for {email} ✓")
