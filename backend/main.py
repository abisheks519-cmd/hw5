"""FastAPI backend for the Campus Customs agent dashboard.

Start it from the backend/ folder (with the HW 5 venv active):
    uvicorn main:app --reload --port 8000

Every shop fact goes through the campus-customs MCP server, like everything else in this project.
This backend has its own MCP connection, started with human approvals turned on, so it is the only
place approve_transaction exists. The agents' connection (inside Team) never has it: agents can
only prepare payments and purchases, and POST /api/transactions/{id}/approve is what moves cash.

Routes (JSON):
  GET  /                                     service info and the route list
  GET  /api/health                           whether the agent team and MCP server are ready
  GET  /api/tickets                          tickets 101-103 with their status and open/resolved state
  POST /api/tickets/{ticket_id}/run          run the agent team on one ticket (background; ?wait=true to block)
  GET  /api/runs                             recent runs, newest first
  GET  /api/runs/{run_id}                    one run: status, outcome, and each agent's contribution
  GET  /api/events                           recent agent events: what each agent said and which tools it used
  GET  /api/transactions                     prepared payments and purchases (default: pending)
  POST /api/transactions/{txn_id}/approve    a person approves one; the only route that changes cash
  GET  /api/cash                             the checking balance from cash_accounts
  POST /api/reset                            restore the database to its original values
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
from collections import Counter
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

HW_DIR = Path(__file__).resolve().parent.parent
if str(HW_DIR) not in sys.path:  # uvicorn is started from backend/, so make the backend package importable
    sys.path.insert(0, str(HW_DIR))

from fastapi import FastAPI, HTTPException, Path as PathParam, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from backend.audit import AUDIT_PATH, AuditTrail
from backend.mcp_connection import campus_customs_client
from backend.models import AuditRecord
from backend.team import Team, new_run_id

DB_ARG = os.environ.get("CC_DB_PATH")  # unset = the MCP server's default, data/campus_customs_new.db
DB_PATH = Path(DB_ARG).resolve() if DB_ARG else HW_DIR / "data" / "campus_customs_new.db"
ORIGINAL_DB = HW_DIR / "data" / "campus_customs.db"
CORS_ORIGINS = [o.strip() for o in os.environ.get(
    "CC_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o.strip()]
AGENTS = ("boss", "inventory", "accounting", "facilities", "customer_service")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------- state

@dataclass
class RunInfo:
    run_id: str
    ticket_id: int
    status: Literal["running", "done", "failed"] = "running"
    started_at: str = field(default_factory=now)
    finished_at: str | None = None
    outcome: dict[str, Any] | None = None
    error: str | None = None
    task: asyncio.Task | None = None

    def public(self) -> dict[str, Any]:
        return {"run_id": self.run_id, "ticket_id": self.ticket_id, "status": self.status, "started_at": self.started_at,
                "finished_at": self.finished_at, "outcome": self.outcome, "error": self.error}


class State:
    team: Team | None = None
    team_error: str | None = None
    mcp: Any = None                       # fastmcp Client with human approvals
    audit = AuditTrail()
    runs: dict[str, RunInfo] = {}
    run_lock = asyncio.Lock()             # the desk works one ticket at a time
    approve_lock = asyncio.Lock()         # approvals one at a time (the database also locks)


state = State()


class ToolProblem(Exception):
    """An MCP tool refused or failed. The message starts with a code for approve_transaction."""


async def mcp_call(tool: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
    result = await state.mcp.call_tool(tool, args or {}, raise_on_error=False)
    if result.is_error:
        raise ToolProblem(result.content[0].text if result.content else f"{tool} failed")
    return result.structured_content


def log(agent: str, action: str, *, ticket_id: int | None = None, run_id: str = "dashboard", **fields: Any) -> None:
    state.audit.append(AuditRecord(run_id=run_id, ticket_id=ticket_id, agent=agent, chain=[], step=0, action=action, **fields))


@asynccontextmanager
async def lifespan(app: FastAPI):
    state.mcp = campus_customs_client(DB_ARG, human_approvals=True)
    await state.mcp.__aenter__()
    try:
        team = Team(db_path=DB_ARG)
        await team.__aenter__()
        state.team = team
    except Exception as exc:  # e.g. no PORTKEY_API_KEY: the read routes still work, runs return 503
        state.team_error = f"{type(exc).__name__}: {exc}"
    try:
        yield
    finally:
        for info in state.runs.values():
            if info.task and not info.task.done():
                info.task.cancel()
        if state.team:
            await state.team.__aexit__(None, None, None)
        await state.mcp.__aexit__(None, None, None)


app = FastAPI(title="Campus Customs agent backend", version="1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_methods=["GET", "POST"], allow_headers=["Content-Type"])


@app.exception_handler(ToolProblem)
async def tool_problem(request: Request, exc: ToolProblem) -> JSONResponse:
    message = str(exc)
    status = 404 if message.startswith("No ") and " with id " in message else 502
    return JSONResponse(status_code=status, content={"detail": message})


@app.exception_handler(Exception)
async def unexpected(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=500, content={"detail": f"{type(exc).__name__}: {exc}"})


# ---------------------------------------------------------------- audit trail reading

_audit_cache: dict[str, Any] = {"key": None, "records": []}


def audit_records() -> list[dict[str, Any]]:
    """The audit trail as a list (cached until the file changes)."""
    try:
        st = AUDIT_PATH.stat()
    except FileNotFoundError:
        return []
    key = (st.st_mtime_ns, st.st_size)
    if _audit_cache["key"] != key:
        try:
            _audit_cache["records"], _audit_cache["key"] = json.loads(AUDIT_PATH.read_text()), key
        except json.JSONDecodeError:  # caught mid-append; the next poll gets the full file
            pass
    return _audit_cache["records"]


def short(value: Any, limit: int = 220) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    return text if len(text) <= limit else text[:limit] + "…"


def event_message(r: dict[str, Any]) -> str:
    """One readable line: what the agent said or did."""
    action, tool, inputs, result = r["action"], r.get("tool"), r.get("inputs"), r.get("result")
    target = tool[4:] if tool and tool.startswith("ask_") else None
    if action == "run_start":
        return f"Started: {short((inputs or {}).get('task', ''), 300)}"
    if action == "model_response":
        text = (result or {}).get("text")
        calls = [c["tool"] for c in (result or {}).get("tool_calls", []) if c["tool"] != "final_result"]
        if text:
            return short(text, 400)
        return f"Decided to call {', '.join(calls)}" if calls else "Wrote its final answer"
    if action == "tool_call":
        return f"Called {tool}({short(inputs, 160)})"
    if action == "tool_result":
        return f"{tool} returned {short(result, 220)}"
    if action == "tool_error":
        return f"{tool} refused: {short(r.get('error') or '', 260)}"
    if action == "delegate":
        return f"Asked {target}: {short((inputs or {}).get('request', ''), 300)}"
    if action == "delegate_result":
        return f"{target} replied: {short((result or {}).get('summary', result), 300)}"
    if action == "delegate_refused":
        return f"Hand-off to {target} refused: {short(r.get('error') or '', 200)}"
    if action == "run_end":
        return f"Finished: {short((result or {}).get('summary', ''), 400)}"
    if action == "approval":
        return f"Approved transaction {(inputs or {}).get('transaction_id')}: {short((result or {}).get('effect', ''), 200)}"
    if action == "reset":
        return "Database reset to its original values"
    if action == "error":
        return f"Stopped: {short(r.get('error') or '', 300)}"
    return action


def event_view(index: int, r: dict[str, Any]) -> dict[str, Any]:
    result = r.get("result")
    if result is not None and len(json.dumps(result, default=str)) > 2000:
        result = short(result, 2000)
    return {"id": index, "ts": r["ts"], "run_id": r["run_id"], "ticket_id": r["ticket_id"], "agent": r["agent"],
            "chain": r["chain"], "step": r["step"], "action": r["action"], "tool": r.get("tool"),
            "message": event_message(r), "inputs": r.get("inputs"), "result": result, "error": r.get("error")}


def contributions(run_id: str) -> list[dict[str, Any]]:
    """What each agent did in one run: who asked it, what it said, which tools it used, what it handed back."""
    by_agent: dict[str, dict[str, Any]] = {}
    for r in audit_records():
        if r["run_id"] != run_id or r["agent"] not in AGENTS:
            continue
        c = by_agent.setdefault(r["agent"], {"agent": r["agent"], "times_asked": 0, "asked_by": [], "summary": None,
                                             "tools_used": Counter(), "handed_off_to": [], "actions_taken": [],
                                             "approvals_needed": [], "reply_draft": None, "errors": []})
        action = r["action"]
        if action == "run_start":
            c["times_asked"] += 1
            if len(r["chain"]) > 1:
                c["asked_by"].append(r["chain"][-2])
        elif action == "tool_call":
            c["tools_used"][r["tool"]] += 1
        elif action == "delegate":
            c["handed_off_to"].append(r["tool"][4:])
        elif action in ("tool_error", "error", "delegate_refused"):
            c["errors"].append(short(r.get("error") or "", 200))
        elif action == "run_end":
            res = r.get("result") or {}
            c["summary"] = res.get("summary")
            c["actions_taken"] += res.get("actions_taken", [])
            c["approvals_needed"] += res.get("approvals_needed", [])
            c["reply_draft"] = res.get("reply_draft") or c["reply_draft"]
    out = []
    for c in by_agent.values():
        c["tools_used"] = [{"tool": t, "calls": n} for t, n in c["tools_used"].items()]
        c["asked_by"] = sorted(set(c["asked_by"]))
        out.append(c)
    return out


# ---------------------------------------------------------------- routes

@app.get("/")
async def index() -> dict[str, Any]:
    return {"service": "Campus Customs agent backend", "docs": "/docs",
            "routes": [f"{m} {r.path}" for r in app.routes if hasattr(r, "methods") and r.path.startswith("/api")
                       for m in sorted(r.methods) if m in ("GET", "POST")]}


@app.get("/api/health")
async def health() -> dict[str, Any]:
    return {"ok": True, "team_ready": state.team is not None, "team_error": state.team_error,
            "database": str(DB_PATH), "running": [i.run_id for i in state.runs.values() if i.status == "running"]}


@app.get("/api/tickets")
async def list_tickets() -> dict[str, Any]:
    """Tickets with their status, open/resolved state, and any run in progress."""
    data = await mcp_call("list_tickets")
    latest: dict[int, RunInfo] = {}
    for info in state.runs.values():
        latest[info.ticket_id] = info  # dicts keep insertion order, so the last one is the newest
    tickets = []
    for t in data["tickets"]:
        run = latest.get(t["id"])
        tickets.append({**t, "state": "resolved" if t["status"] == "resolved" else "open",
                        "latest_run": run.public() if run else None})
    return {"shop_date": data["shop_date"], "tickets": tickets}


async def execute_run(info: RunInfo) -> None:
    """Run the team on one ticket. When the run finishes, the ticket is marked resolved."""
    async with state.run_lock:
        try:
            outcome = await state.team.handle_ticket(info.ticket_id, run_id=info.run_id)
            info.outcome = outcome.model_dump()
            ticket = await mcp_call("get_ticket", {"ticket_id": info.ticket_id})
            if ticket["status"] != "resolved":  # the run finished, so its work on the ticket is done
                note = (f"Agent run {info.run_id} finished; marked resolved. The Boss had set {ticket['status']}. "
                        f"Open owner decisions: {len(outcome.approvals_needed)}.")
                args = {"ticket_id": info.ticket_id, "status": "resolved", "note": note, "author": "dashboard"}
                log("team", "tool_call", ticket_id=info.ticket_id, run_id=info.run_id, tool="update_ticket", inputs=args)
                result = await mcp_call("update_ticket", args)
                log("team", "tool_result", ticket_id=info.ticket_id, run_id=info.run_id, tool="update_ticket",
                    result={"status": result["status"]})
            info.status = "done"
        except Exception as exc:
            info.status, info.error = "failed", f"{type(exc).__name__}: {exc}"
        finally:
            info.finished_at = now()


@app.post("/api/tickets/{ticket_id}/run", status_code=202)
async def run_ticket(ticket_id: int = PathParam(ge=1),
                     wait: bool = Query(False, description="Wait for the run to finish instead of returning right away")) -> JSONResponse:
    """Start the agent team on one ticket. Returns 202 with the run id; poll /api/runs/{run_id} or /api/events."""
    if state.team is None:
        raise HTTPException(503, f"The agent team isn't available: {state.team_error}")
    await mcp_call("get_ticket", {"ticket_id": ticket_id})  # 404 if the ticket doesn't exist
    running = next((i for i in state.runs.values() if i.status == "running"), None)
    if running or state.run_lock.locked():
        raise HTTPException(409, f"A run is already in progress (run {running.run_id if running else '?'} on ticket "
                                 f"{running.ticket_id if running else '?'}). Wait for it to finish.")
    info = RunInfo(run_id=new_run_id(), ticket_id=ticket_id)
    state.runs[info.run_id] = info
    info.task = asyncio.create_task(execute_run(info))
    if wait:
        await info.task
        return JSONResponse(status_code=200, content={**info.public(), "contributions": contributions(info.run_id)})
    return JSONResponse(status_code=202, content=info.public())


@app.get("/api/runs")
async def list_runs(ticket_id: int | None = Query(None, ge=1)) -> dict[str, Any]:
    runs = [i.public() for i in reversed(state.runs.values()) if ticket_id is None or i.ticket_id == ticket_id]
    return {"runs": runs}


@app.get("/api/runs/{run_id}")
async def get_run(run_id: str = PathParam(pattern=r"^run-[0-9a-f]{12}$")) -> dict[str, Any]:
    """One run's status and outcome, plus a summary of each agent's contribution (from the audit trail)."""
    info = state.runs.get(run_id)
    if info is not None:
        return {**info.public(), "contributions": contributions(run_id)}
    records = [r for r in audit_records() if r["run_id"] == run_id]  # a run from before a server restart
    if not records:
        raise HTTPException(404, f"No run {run_id}.")
    boss_end = next((r for r in reversed(records) if r["agent"] == "boss" and r["action"] in ("run_end", "error")
                     and r["chain"] == ["boss"]), None)
    status = "running" if boss_end is None else ("done" if boss_end["action"] == "run_end" else "failed")
    return {"run_id": run_id, "ticket_id": records[0]["ticket_id"], "status": status, "started_at": records[0]["ts"],
            "finished_at": boss_end["ts"] if boss_end else None,
            "outcome": boss_end["result"] if boss_end and boss_end["action"] == "run_end" else None,
            "error": boss_end["error"] if boss_end and boss_end["action"] == "error" else None,
            "contributions": contributions(run_id)}


@app.get("/api/events")
async def events(ticket_id: int | None = Query(None, ge=1), run_id: str | None = Query(None, max_length=40),
                 after: int = Query(-1, ge=-1, description="Only events with an id above this (for polling)"),
                 limit: int = Query(100, ge=1, le=500),
                 include_model_requests: bool = Query(False)) -> dict[str, Any]:
    """Recent agent events: what each agent said, the tools it called and their results, hand-offs, and errors."""
    records = audit_records()
    picked = []
    for i in range(len(records) - 1, after, -1):  # newest first, stop at `after`
        r = records[i]
        if (ticket_id is not None and r["ticket_id"] != ticket_id) or (run_id and r["run_id"] != run_id):
            continue
        if r["action"] == "model_request" and not include_model_requests:
            continue
        picked.append(event_view(i, r))
        if len(picked) >= limit:
            break
    picked.reverse()  # oldest first, so a feed can append them in order
    return {"events": picked, "last_id": len(records) - 1}


@app.get("/api/transactions")
async def transactions(status: Literal["pending", "approved", "all"] = Query("pending")) -> dict[str, Any]:
    """Payments and purchases the agents prepared, waiting for a person to approve them."""
    return await mcp_call("list_pending_transactions", {"status": status})


class ApproveRequest(BaseModel):
    approved_by: str = Field(min_length=1, max_length=80, description="Name of the person clicking Approve")

    @field_validator("approved_by")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("approved_by can't be blank")
        return v.strip()


APPROVAL_STATUS = {"not_found": 404, "already_approved": 409, "conflict": 409, "insufficient_funds": 409, "invalid": 422}


@app.post("/api/transactions/{txn_id}/approve")
async def approve(body: ApproveRequest, txn_id: int = PathParam(ge=1)) -> dict[str, Any]:
    """A person approves a prepared payment or purchase. This is the only route that changes cash.

    A second click on the same transaction gets 409: the MCP server flips it from pending to approved
    inside one database transaction, so it can never be paid twice.
    """
    async with state.approve_lock:
        try:
            receipt = await mcp_call("approve_transaction", {"transaction_id": txn_id, "approved_by": body.approved_by})
        except ToolProblem as exc:
            code, _, message = str(exc).partition(": ")
            raise HTTPException(APPROVAL_STATUS.get(code, 502), {"code": code if code in APPROVAL_STATUS else "error",
                                                                  "message": message or str(exc)})
    log("human", "approval", ticket_id=receipt["transaction"]["ticket_id"], tool="approve_transaction",
        inputs={"transaction_id": txn_id, "approved_by": body.approved_by}, result=receipt)
    return receipt


@app.get("/api/cash")
async def cash() -> dict[str, Any]:
    """The checking balance from cash_accounts."""
    data = await mcp_call("get_cash_position")
    checking = next((a for a in data["accounts"] if a["name"] == "checking"), None)
    if checking is None:
        raise HTTPException(404, "There is no checking account in cash_accounts.")
    return {"account": "checking", "balance": checking["balance"], "as_of": checking["as_of"], "shop_date": data["shop_date"]}


@app.post("/api/reset")
async def reset() -> dict[str, Any]:
    """Restore data/campus_customs_new.db to the original data/campus_customs.db for a fresh run.

    The audit trail is append-only and is not cleared; the reset is logged in it.
    """
    if state.run_lock.locked() or any(i.status == "running" for i in state.runs.values()):
        raise HTTPException(409, "A run is in progress. Reset after it finishes.")
    if DB_PATH.resolve() == ORIGINAL_DB.resolve():
        raise HTTPException(409, "Refusing to reset: the working database is the original file.")
    async with state.approve_lock:
        if Path(f"{DB_PATH}-journal").exists():
            raise HTTPException(409, "The database is in the middle of a write. Try the reset again in a moment.")
        # Copy the original next to the working file, then swap it in with one atomic rename. The result is
        # byte-identical to data/campus_customs.db, and no reader ever sees a half-written file.
        tmp = DB_PATH.with_name(DB_PATH.name + ".reset-tmp")
        shutil.copyfile(ORIGINAL_DB, tmp)
        os.replace(tmp, DB_PATH)
    state.runs.clear()
    log("human", "reset", inputs={"from": "data/campus_customs.db", "to": str(DB_PATH)})
    tickets = await mcp_call("list_tickets")
    balance = await cash()
    return {"reset": True, "database": str(DB_PATH), "checking_balance": balance["balance"],
            "tickets": [{"id": t["id"], "status": t["status"]} for t in tickets["tickets"]]}
