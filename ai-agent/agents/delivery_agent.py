import logging
import openai
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent, ToolNode
from .tools import send_summary_email, create_board_dashboard
from .structure_agent import BoardStructure

logger = logging.getLogger(__name__)


def _build_prompt(
    name: str,
    email: str,
    company: str,
    summary: dict,
    board_name: str,
    company_summary: str,
    structure: BoardStructure,
    created_items: list[str],
) -> str:
    return f"""
Customer: {name} <{email}> — {company}, team size: {summary.get('team_size', 0)}
Board ID: {structure.board_id}
Board name: "{board_name}"
Company summary: "{company_summary}"
Created items: {created_items}
Created columns: {list(structure.column_map.keys())}

=== EXECUTION PLAN ===

STEP 1 — Create dashboard
  Call create_board_dashboard with:
  - board_id:   "{structure.board_id}"
  - board_name: "{board_name}"
  - use_case:   "{summary.get('use_case', '')}"
  - pain_point: "{summary.get('pain_point', '')}"
  Result is JSON: {{"dashboard_id": "...", "widgets": [...]}}
  Save dashboard_id and widgets list.

STEP 2 — Send email
  Call send_summary_email with:
  - to:               {email}
  - name:             {name}
  - board_id:         "{structure.board_id}"
  - board_name:       "{board_name}"
  - company_summary:  "{company_summary}"
  - columns:          {list(structure.column_map.keys())}
  - item_names:       {created_items}
  - dashboard_id:     <dashboard_id from step 1>
  - dashboard_widgets: <widgets list from step 1>
  - team_size:        {summary.get('team_size', 0)}

RULES:
- Call ONE tool at a time
- If dashboard creation fails, still send the email without dashboard fields
"""


async def run_delivery_agent(
    name: str,
    email: str,
    company: str,
    summary: dict,
    board_name: str,
    company_summary: str,
    structure: BoardStructure,
    created_items: list[str],
    monday_tools: list,
) -> None:
    needed = {"get_board_info"}
    tools = [t for t in monday_tools if t.name in needed] + [
        create_board_dashboard, send_summary_email
    ]

    def _handle_tool_error(e: Exception) -> str:
        cause = getattr(e, "exceptions", [e])[0] if hasattr(e, "exceptions") else e
        msg = f"Tool call failed: {type(cause).__name__}: {cause}"
        print(f"[Delivery] Tool error (handled): {msg}")
        return f"{msg}. Continue with the next step."

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    tool_node = ToolNode(tools, handle_tool_errors=_handle_tool_error)
    agent = create_react_agent(llm, tool_node)

    system_prompt = (
        "You are a Monday.com delivery specialist. "
        "Your job is to create a dashboard and send the customer a summary email. "
        "Call ONE tool at a time. "
        "If dashboard creation fails, still send the email without dashboard fields."
    )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=5, max=20),
        retry=retry_if_exception_type((openai.RateLimitError, openai.APIConnectionError)),
        reraise=True,
    )
    async def invoke():
        return await agent.ainvoke(
            {"messages": [HumanMessage(content=system_prompt + "\n\n" + _build_prompt(
                name, email, company, summary, board_name, company_summary, structure, created_items
            ))]}
        )

    try:
        print("[Delivery] Running agent...")
        await invoke()
        print("[Delivery] DONE ✓")
    except Exception as e:
        print(f"[Delivery] ERROR: {e}")
        logger.error(f"Delivery agent failed for {email}: {e}", exc_info=True)
