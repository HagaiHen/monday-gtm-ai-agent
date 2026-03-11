import json
import os
import re
from langchain_core.tools import tool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

MONDAY_ACCOUNT_SLUG = os.getenv("MONDAY_ACCOUNT_SLUG", "app")  # e.g. "hagaihen7s-team"
MONDAY_API_TOKEN = os.getenv("MONDAY_API_TOKEN", "")

_redis_client = None


def init_redis(url: str) -> None:
    import redis.asyncio as aioredis
    global _redis_client
    _redis_client = aioredis.from_url(url, decode_responses=True)


async def _get_redis():
    global _redis_client
    if _redis_client is None:
        import redis.asyncio as aioredis
        url = os.getenv("REDIS_URL", "redis://localhost:6379")
        _redis_client = aioredis.from_url(url, decode_responses=True)
    return _redis_client


@tool
async def send_summary_email(
    to: str,
    name: str,
    board_id: str,
    board_name: str,
    company_summary: str,
    columns: list[str],
    item_names: list[str],
    dashboard_id: str = "",
    dashboard_widgets: list[str] = [],
    team_size: int = 0,
) -> bool:
    """Send a summary email to the customer with their Monday.com board and dashboard links.

    Args:
        to: Customer's email address
        name: Customer's name
        board_id: The Monday.com board ID returned by create_board (used to construct the URL)
        board_name: The name of the board that was created
        company_summary: 1-2 sentence summary of what the company does (from research)
        columns: List of column names added to the board
        item_names: List of item names created on the board
        dashboard_id: The Monday.com dashboard ID from create_board_dashboard result JSON
        dashboard_widgets: List of widget names from create_board_dashboard result JSON
        team_size: Number of people on the team (used to recommend a pricing plan)

    Returns:
        True if email sent successfully
    """
    board_url = f"https://{MONDAY_ACCOUNT_SLUG}.monday.com/boards/{board_id}"
    dashboard_url = f"https://{MONDAY_ACCOUNT_SLUG}.monday.com/overviews/{dashboard_id}" if dashboard_id else ""

    print(f"\n[Email] Publishing to email:send — {to}")
    print(f"[Email] Board:     {board_name} ({board_url})")
    if dashboard_url:
        print(f"[Email] Dashboard: {dashboard_url}")

    client = await _get_redis()
    await client.publish("email:send", json.dumps({
        "to": to,
        "name": name,
        "board_url": board_url,
        "board_name": board_name,
        "company_summary": company_summary,
        "columns": columns,
        "item_names": item_names,
        "dashboard_url": dashboard_url,
        "dashboard_widgets": dashboard_widgets,
        "team_size": team_size,
    }))
    return True


async def _create_widget_safe(by_name: dict, **kwargs) -> bool:
    """Create a widget, returning False on failure without raising."""
    try:
        await by_name["create_widget"].ainvoke(kwargs)
        print(f"[Dashboard] Created {kwargs['widget_kind']} widget: {kwargs['widget_name']}")
        return True
    except Exception as e:
        print(f"[Dashboard] Widget '{kwargs['widget_name']}' failed: {e}")
        return False


@tool
async def create_board_dashboard(board_id: str, board_name: str, use_case: str = "", pain_point: str = "") -> str:
    """Create a Monday.com dashboard with widgets customized to the board's columns and use case.

    Args:
        board_id: The Monday.com board ID (as returned by create_board)
        board_name: The board name, used as the dashboard title
        use_case: The customer's use case (e.g. "merchant onboarding pipeline tracking")
        pain_point: The customer's pain point (e.g. "deals close but onboarding gets lost")

    Returns:
        Summary of what was created
    """
    try:
        mcp_client = MultiServerMCPClient({
            "monday": {
                "transport": "streamable_http",
                "url": "https://mcp.monday.com/mcp",
                "headers": {"Authorization": f"Bearer {MONDAY_API_TOKEN}"},
            }
        })
        tools = await mcp_client.get_tools()
        by_name = {t.name: t for t in tools}

        # Get board info — workspace_id + column map
        board_info_raw = await by_name["get_board_info"].ainvoke({"boardId": int(board_id)})
        board_text = board_info_raw[0]["text"] if isinstance(board_info_raw, list) else str(board_info_raw)
        board_data = json.loads(board_text)
        board = board_data["board"]
        workspace_id = str(board["workspace"]["id"])
        columns = board["columns"]
        bid = str(board_id)

        # Index columns by type
        by_type: dict[str, list[dict]] = {}
        for col in columns:
            by_type.setdefault(col["type"], []).append(col)

        status_col = next(iter(by_type.get("status", [])), None)
        timeline_col = next(iter(by_type.get("timeline", [])), None)
        people_col = next(iter(by_type.get("people", [])), None)

        if not status_col:
            return "No status column found — dashboard skipped"

        status_col_id = status_col["id"]
        # Find the label marked as done (is_done=true), fallback to "Done"
        done_label = "Done"
        for lbl in status_col.get("settings", {}).get("labels", []):
            if lbl.get("is_done"):
                done_label = lbl["label"]
                break

        print(f"[Dashboard] status_col={status_col_id}, done='{done_label}', "
              f"timeline={'yes' if timeline_col else 'no'}, people={'yes' if people_col else 'no'}")

        # Build the catalogue of widgets we CAN create given available columns
        catalogue: list[dict] = [
            {
                "id": "battery",
                "name": "Overall Progress",
                "description": "Battery bar showing % of items marked Done. Best when the goal is tracking completion rate (e.g. onboarding, project delivery).",
            },
            {
                "id": "status_pie",
                "name": "Status Breakdown",
                "description": "Pie chart showing distribution across all status values. Best when there are 3+ status categories the user cares about (e.g. In Review, Approved, Rejected).",
            },
            {
                "id": "stage_bar",
                "name": "Items by Stage",
                "description": "Bar chart showing item count per pipeline stage / board group.",
            },
        ]
        if people_col:
            catalogue.append({
                "id": "assignee_bar",
                "name": "Workload by Assignee",
                "description": "Bar chart showing how many items each team member owns",
                "always": False,
            })
        if timeline_col:
            catalogue.append({
                "id": "gantt",
                "name": "Timeline View",
                "description": "Gantt chart visualising item timelines — best for project/scheduling use cases",
                "always": False,
            })

        # Ask LLM to pick which widgets to include
        catalogue_text = "\n".join(
            f"- {w['id']}: {w['name']} — {w['description']}" for w in catalogue
        )

        class WidgetSelection(BaseModel):
            selected_ids: list[str]
            reasoning: str

        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        selection: WidgetSelection = await llm.with_structured_output(WidgetSelection).ainvoke([
            SystemMessage(content=(
                "You are a Monday.com dashboard designer. "
                "Pick 2-3 widgets that best fit the customer's use case. "
                "IMPORTANT: 'battery' and 'status_pie' show overlapping information — pick at most ONE of them. "
                "Only include a widget if it genuinely adds value."
            )),
            HumanMessage(content=f"""Customer use case: {use_case}
Pain point: {pain_point}
Board name: {board_name}

Available widgets (pick 2-3, choose at most one of battery/status_pie):
{catalogue_text}

Return the selected widget IDs and a brief reasoning."""),
        ])
        print(f"[Dashboard] LLM selected: {selection.selected_ids} — {selection.reasoning}")

        selected_ids = set(selection.selected_ids)

        # Create dashboard
        dash_raw = await by_name["create_dashboard"].ainvoke({
            "name": f"{board_name} — Overview",
            "workspace_id": workspace_id,
            "board_ids": [bid],
        })
        dash_text = dash_raw[0]["text"] if isinstance(dash_raw, list) else str(dash_raw)
        dash_match = re.search(r"ID:\s*(\d+)", dash_text)
        if not dash_match:
            return f"Dashboard creation failed: {dash_text[:200]}"
        dashboard_id = dash_match.group(1)
        print(f"[Dashboard] Created dashboard {dashboard_id}")

        created: list[str] = []

        if "battery" in selected_ids:
            ok = await _create_widget_safe(
                by_name,
                widget_kind="BATTERY",
                widget_name="Overall Progress",
                parent_container_id=dashboard_id,
                parent_container_type="DASHBOARD",
                settings={
                    "done_text": done_label,
                    "battery_data": {"status_column_ids_per_board": {bid: [status_col_id]}},
                },
            )
            if ok: created.append("Battery (progress)")

        if "status_pie" in selected_ids:
            ok = await _create_widget_safe(
                by_name,
                widget_kind="CHART",
                widget_name="Status Breakdown",
                parent_container_id=dashboard_id,
                parent_container_type="DASHBOARD",
                settings={
                    "graph_type": "pie",
                    "x_axis_columns": {bid: [status_col_id]},
                    "y_axis_columns": {bid: ["default-label-count"]},
                    "x_axis_group_by": "color",
                    "y_axis_group_by": "default-label-count",
                },
            )
            if ok: created.append("Chart: status pie")

        if "stage_bar" in selected_ids:
            ok = await _create_widget_safe(
                by_name,
                widget_kind="CHART",
                widget_name="Items by Stage",
                parent_container_id=dashboard_id,
                parent_container_type="DASHBOARD",
                settings={
                    "graph_type": "bar",
                    "x_axis_columns": {bid: ["group"]},
                    "y_axis_columns": {bid: ["default-label-count"]},
                    "x_axis_group_by": "group",
                    "y_axis_group_by": "default-label-count",
                },
            )
            if ok: created.append("Chart: items by stage")

        if "assignee_bar" in selected_ids and people_col:
            ok = await _create_widget_safe(
                by_name,
                widget_kind="CHART",
                widget_name="Workload by Assignee",
                parent_container_id=dashboard_id,
                parent_container_type="DASHBOARD",
                settings={
                    "graph_type": "bar",
                    "x_axis_columns": {bid: [people_col["id"]]},
                    "y_axis_columns": {bid: ["default-label-count"]},
                    "x_axis_group_by": "multiple-person",
                    "y_axis_group_by": "default-label-count",
                },
            )
            if ok: created.append("Chart: workload by assignee")

        if "gantt" in selected_ids and timeline_col:
            ok = await _create_widget_safe(
                by_name,
                widget_kind="GANTT",
                widget_name="Timeline View",
                parent_container_id=dashboard_id,
                parent_container_type="DASHBOARD",
                settings={
                    "columnIdsByBoardId": {bid: [timeline_col["id"]]},
                    "colorByIdPerBoardId": {bid: ["group"]},
                    "color_by_type": "group",
                    "show_today_line": True,
                },
            )
            if ok: created.append("Gantt: timeline")

        import json as _json
        return _json.dumps({"dashboard_id": dashboard_id, "widgets": created})

    except Exception as e:
        print(f"[Dashboard] ERROR: {e}")
        return f"Dashboard creation failed: {e}"
