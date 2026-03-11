import re
import json
import logging
import openai
from dataclasses import dataclass
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent, ToolNode
from .researcher import BoardBlueprint

logger = logging.getLogger(__name__)

GROUP_COLORS = [
    "#579bfc", "#00c875", "#fdab3d", "#df2f4a", "#9d50dd",
    "#ffcb00", "#66ccff", "#037f4c", "#ff5ac4", "#7f5347",
]


@dataclass
class BoardStructure:
    board_id: str
    group_map: dict[str, str]   # group_name → group_id
    column_map: dict[str, str]  # column_title → column_id


def _parse_structure_from_messages(messages: list) -> tuple[str | None, dict, dict]:
    """
    Extract board_id, group_map, and column_map from the agent's message history.
    More reliable than asking the LLM to pass complex dicts as tool arguments.
    """
    board_id = None
    group_map: dict[str, str] = {}
    column_map: dict[str, str] = {}

    # Build a map of tool_call_id → {name, args} from AI messages
    call_index: dict[str, dict] = {}
    for msg in messages:
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                call_index[tc.get("id", "")] = {"name": tc["name"], "args": tc.get("args", {})}

    for msg in messages:
        # Skip non-tool-result messages
        if not (hasattr(msg, "name") and msg.name):
            continue

        content = ""
        if isinstance(msg.content, list):
            for block in msg.content:
                if isinstance(block, dict):
                    content += block.get("text", "")
        else:
            content = str(msg.content)

        tool_id = getattr(msg, "tool_call_id", "")
        call = call_index.get(tool_id, {})
        call_name = call.get("name") or msg.name
        call_args = call.get("args", {})

        if call_name == "create_board":
            m = re.search(r"Board (\d+)", content)
            if m:
                board_id = m.group(1)

        elif call_name == "create_group":
            group_name = call_args.get("groupName", "")
            m = re.search(r"ID:\s*([a-z0-9_]+)\)", content)
            if m and group_name:
                group_map[group_name] = m.group(1)

        elif call_name == "get_board_info":
            try:
                data = json.loads(content)
                for col in data.get("board", {}).get("columns", []):
                    title = col.get("title", "")
                    col_id = col.get("id", "")
                    if title and col_id and title != "Name":
                        column_map[title] = col_id
            except Exception:
                pass

    return board_id, group_map, column_map


def _build_prompt(blueprint: BoardBlueprint) -> str:
    groups_text = "\n".join(
        f'  - name: "{g.name}", color: "{GROUP_COLORS[i % len(GROUP_COLORS)]}"'
        for i, g in enumerate(blueprint.groups)
    )
    columns_text = "\n".join(
        f'  - title: "{c.title}", type: {c.column_type}'
        for c in blueprint.columns
    )
    return f"""
Board name: "{blueprint.board_name}"

GROUPS (in order):
{groups_text}

COLUMNS:
{columns_text}

=== EXECUTION PLAN ===

STEP 1 — Create the board
  - create_board(boardName="{blueprint.board_name}") → note the board_id

STEP 2 — Enable subitems
  - all_monday_api with query (replace BOARD_ID with the actual integer board_id):
    mutation {{ create_column(board_id: BOARD_ID, title: "Subitems", column_type: subtasks) {{ id }} }}

STEP 3 — Create groups
  - For each group: create_group(boardId, groupName, groupColor)

STEP 4 — Create columns
  - For each column: create_column(boardId, columnTitle, columnType)

STEP 5 — Get board info
  - get_board_info(boardId) — this is required to confirm all columns were created

STEP 6 — Done
  - Call capture_done() to signal completion

RULES:
- Call ONE tool at a time — wait for result before the next
- If a tool call fails, log it and continue
"""


async def run_structure_agent(
    blueprint: BoardBlueprint,
    monday_tools: list,
) -> BoardStructure | None:
    done_flag: dict = {}

    @tool
    def capture_done() -> str:
        """Call this as the final step to signal that board setup is complete."""
        done_flag["done"] = True
        return "Board setup complete."

    needed = {"create_board", "create_group", "create_column", "get_board_info", "all_monday_api"}
    tools = [t for t in monday_tools if t.name in needed] + [capture_done]

    def _handle_tool_error(e: Exception) -> str:
        cause = getattr(e, "exceptions", [e])[0] if hasattr(e, "exceptions") else e
        msg = f"Tool call failed: {type(cause).__name__}: {cause}"
        print(f"[Structure] Tool error (handled): {msg}")
        return f"{msg}. Continue with the next step."

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    tool_node = ToolNode(tools, handle_tool_errors=_handle_tool_error)
    agent = create_react_agent(llm, tool_node)

    system_prompt = (
        "You are a Monday.com board structure specialist. "
        "Your ONLY job is to create the board, groups, and columns — nothing else. "
        "Call ONE tool at a time. Wait for its result before calling the next. "
        "At the end, call capture_done() to signal completion. "
        "If a tool call fails, log it and continue."
    )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=5, max=20),
        retry=retry_if_exception_type((openai.RateLimitError, openai.APIConnectionError)),
        reraise=True,
    )
    async def invoke():
        return await agent.ainvoke(
            {"messages": [HumanMessage(content=system_prompt + "\n\n" + _build_prompt(blueprint))]}
        )

    result = None
    try:
        print("[Structure] Running agent...")
        result = await invoke()
    except Exception as e:
        print(f"[Structure] ERROR: {e}")
        logger.error(f"Structure agent failed: {e}", exc_info=True)

    if result is None:
        return None

    # Parse board_id, group_map, column_map from message history
    board_id, group_map, column_map = _parse_structure_from_messages(result["messages"])

    if not board_id:
        print("[Structure] FAILED — board_id not found in message history")
        return None

    print(f"[Structure] Parsed board_id={board_id}, "
          f"{len(group_map)} groups, {len(column_map)} columns")

    return BoardStructure(
        board_id=board_id,
        group_map=group_map,
        column_map=column_map,
    )
