import re
import logging
import openai
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent, ToolNode
from .researcher import BoardBlueprint
from .structure_agent import BoardStructure

logger = logging.getLogger(__name__)

STATUS_INDEX = {"Working on it": 0, "Done": 1, "Stuck": 2}


def _build_prompt(blueprint: BoardBlueprint, structure: BoardStructure) -> str:
    col_id_map = {t.lower(): cid for t, cid in structure.column_map.items()}

    def _find_col(title: str) -> str | None:
        return col_id_map.get(title.lower())

    def _item_column_values_json(item) -> str:
        parts: list[str] = []

        # Status
        status_col = _find_col("status")
        if status_col:
            idx = STATUS_INDEX.get(item.status, 0)
            parts.append(f'"{status_col}": {{"index": {idx}}}')

        # Priority
        priority_col = _find_col("priority")
        if priority_col:
            parts.append(f'"{priority_col}": "{item.priority}"')

        # Timeline
        timeline_col = next(
            (cid for t, cid in structure.column_map.items() if "timeline" in t.lower()),
            None,
        )
        if timeline_col and item.timeline_start and item.timeline_end:
            parts.append(
                f'"{timeline_col}": {{"from": "{item.timeline_start}", "to": "{item.timeline_end}"}}'
            )

        # Extra column values from blueprint
        for cv in (item.column_values or []):
            cid = _find_col(cv.title)
            if not cid:
                continue
            value = cv.value
            if "email" in cv.title.lower() or ("@" in value and "." in value):
                parts.append(f'"{cid}": {{"email": "{value}", "text": "{value}"}}')
            elif "phone" in cv.title.lower():
                digits = re.sub(r"[^\d+]", "", value)
                parts.append(f'"{cid}": {{"phone": "{digits}", "countryShortName": "US"}}')
            else:
                escaped = value.replace('"', '\\"')
                parts.append(f'"{cid}": "{escaped}"')

        return "{" + ", ".join(parts) + "}"

    items_text = "\n\n".join(
        f'ITEM: "{item.name}"\n'
        f'  group_id: "{structure.group_map.get(item.group, "UNKNOWN")}"\n'
        f'  columnValues (copy exactly): {_item_column_values_json(item)}\n'
        f'  subitems: {item.subitems}\n'
        f'  update: "{item.update_note}"'
        for item in blueprint.items
    )

    return f"""
Board ID: {structure.board_id}

ITEMS TO CREATE:
{items_text}

=== EXECUTION PLAN ===

For EACH item above, complete ALL of these sub-steps before moving to the next item:

a) create_item(boardId={structure.board_id}, groupId=<group_id>, name=<item name>, columnValues="{{}}")

b) change_item_column_values(boardId, itemId, columnValues)
   Use the exact columnValues JSON shown above for this item — copy it as-is.
   Do NOT change the column IDs or values.

c) For each subitem name, call all_monday_api with:
   mutation {{ create_subitem(parent_item_id: ITEM_ID, item_name: "SUBITEM_NAME") {{ id }} }}

d) create_update(itemId, updateText) using the update text shown above

After ALL items are done, call capture_items with the list of item names you successfully created.

RULES:
- Call ONE tool at a time — wait for result before the next
- Always pass columnValues="{{}}" in create_item (set values in step b only)
- If a tool call fails, log it and continue — never skip an entire item
"""


async def run_content_agent(
    blueprint: BoardBlueprint,
    structure: BoardStructure,
    monday_tools: list,
) -> list[str]:
    created_items: list[str] = []

    @tool
    def capture_items(item_names: list[str]) -> str:
        """Call this after ALL items have been created.

        Args:
            item_names: List of item names that were successfully created on the board
        """
        created_items.extend(item_names)
        print(f"[Content] Captured {len(item_names)} items: {item_names}")
        return f"Captured {len(item_names)} items."

    needed = {"create_item", "change_item_column_values", "all_monday_api", "create_update"}
    tools = [t for t in monday_tools if t.name in needed] + [capture_items]

    def _handle_tool_error(e: Exception) -> str:
        cause = getattr(e, "exceptions", [e])[0] if hasattr(e, "exceptions") else e
        msg = f"Tool call failed: {type(cause).__name__}: {cause}"
        print(f"[Content] Tool error (handled): {msg}")
        return f"{msg}. Continue with the next step."

    llm = ChatOpenAI(model="gpt-4o", temperature=0)
    tool_node = ToolNode(tools, handle_tool_errors=_handle_tool_error)
    agent = create_react_agent(llm, tool_node)

    system_prompt = (
        "You are a Monday.com content specialist. "
        "Your ONLY job is to create items and populate their column values, subitems, and updates. "
        "The board structure already exists — do NOT create boards, groups, or columns. "
        "Call ONE tool at a time. Work through items sequentially — "
        "complete all sub-steps (a-d) for one item before starting the next. "
        "At the end, call capture_items with ALL successfully created item names."
    )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=5, max=20),
        retry=retry_if_exception_type((openai.RateLimitError, openai.APIConnectionError)),
        reraise=True,
    )
    async def invoke():
        return await agent.ainvoke(
            {"messages": [HumanMessage(content=system_prompt + "\n\n" + _build_prompt(blueprint, structure))]}
        )

    try:
        print("[Content] Running agent...")
        await invoke()
    except Exception as e:
        print(f"[Content] ERROR: {e}")
        logger.error(f"Content agent failed: {e}", exc_info=True)

    return created_items
