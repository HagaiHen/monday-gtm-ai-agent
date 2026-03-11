"""
Explore all available Monday MCP tools and their schemas.
Run: docker-compose exec ai-agent python explore_mcp.py
"""
import asyncio
import json
import os
from dotenv import load_dotenv
load_dotenv()

from langchain_mcp_adapters.client import MultiServerMCPClient

MONDAY_API_TOKEN = os.getenv("MONDAY_API_TOKEN", "")

async def main():
    client = MultiServerMCPClient({
        "monday": {
            "transport": "streamable_http",
            "url": "https://mcp.monday.com/mcp",
            "headers": {"Authorization": f"Bearer {MONDAY_API_TOKEN}"},
        }
    })

    tools = await client.get_tools()
    print(f"\n{'='*60}")
    print(f"  Monday MCP — {len(tools)} tools available")
    print(f"{'='*60}\n")

    for tool in sorted(tools, key=lambda t: t.name):
        print(f"┌─ {tool.name}")
        print(f"│  {tool.description}")
        schema = tool.args_schema.schema() if hasattr(tool.args_schema, 'schema') else {}
        props = schema.get("properties", {})
        required = schema.get("required", [])
        if props:
            print(f"│  Args:")
            for arg_name, arg_def in props.items():
                req = " *" if arg_name in required else ""
                arg_type = arg_def.get("type", arg_def.get("anyOf", "?"))
                desc = arg_def.get("description", "")
                print(f"│    {arg_name}{req}: {arg_type} — {desc[:80]}")
        print(f"└{'─'*50}\n")

if __name__ == "__main__":
    asyncio.run(main())
