"""The only way to shop data: the campus-customs MCP server.

The server command comes from .mcp.json (the same entry Claude Code uses), so the agents, the
FastAPI backend, and the vibe coder all start the same server. Each server process gets only the
settings it needs, not this process's whole environment (so it never sees the model key).

There are two kinds of connection:
- campus_customs_toolset(): for the agents. It never has approve_transaction, so no agent can
  move money; agents can only prepare payments and purchases.
- campus_customs_client(human_approvals=True): for the FastAPI backend only. Its server process
  adds approve_transaction, which the dashboard's Approve button calls.
"""

import json
import os
from pathlib import Path

from fastmcp import Client
from fastmcp.client.transports import StdioTransport
from pydantic_ai.mcp import MCPToolset

HW_DIR = Path(__file__).resolve().parent.parent
SERVER_NAME = "campus-customs"


def _transport(db_path: str | Path | None, human_approvals: bool) -> StdioTransport:
    entry = json.loads((HW_DIR / ".mcp.json").read_text())["mcpServers"][SERVER_NAME]
    in_hw = lambda p: str(HW_DIR / p) if (HW_DIR / p).exists() else p  # .mcp.json paths are relative to HW 5
    env = {"PATH": os.environ.get("PATH", ""), **entry.get("env", {})}
    if db_path:
        env["CC_DB_PATH"] = str(Path(db_path).resolve())
    if human_approvals:
        env["CC_HUMAN_APPROVALS"] = "1"
    return StdioTransport(in_hw(entry["command"]), [in_hw(a) for a in entry.get("args", [])], env=env, cwd=str(HW_DIR))


def campus_customs_toolset(db_path: str | Path | None = None) -> MCPToolset:
    """The agents' connection (db_path defaults to data/campus_customs_new.db). No approval tool."""
    # "failed": a tool refusal goes back to the model as a failed result it can explain,
    # instead of crashing the run or prompting blind retries.
    return MCPToolset(Client(_transport(db_path, human_approvals=False)), id=SERVER_NAME, tool_error_behavior="failed")


def campus_customs_client(db_path: str | Path | None = None, human_approvals: bool = False) -> Client:
    """A plain FastMCP client for the backend. human_approvals=True adds approve_transaction."""
    return Client(_transport(db_path, human_approvals))
