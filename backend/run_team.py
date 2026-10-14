"""Run the Campus Customs agent team from the HW 5 folder.

  .venv/bin/python -m backend.run_team                  # the Boss works every open ticket
  .venv/bin/python -m backend.run_team --ticket 102     # one ticket
  .venv/bin/python -m backend.run_team --agent inventory --task "How many CC-HOOD-NAVY size M are on hand?"

  --db PATH                 database for the MCP server (default data/campus_customs_new.db)
Agents never move money: payments and purchases are only prepared, and a person approves them
on the dashboard (POST /api/transactions/{id}/approve). Every step is appended to output/audit_trail.json.
"""

import argparse
import asyncio

from backend.agents import SPECS
from backend.team import Team


async def main(args: argparse.Namespace) -> None:
    async with Team(db_path=args.db) as team:
        if args.agent:
            out = await team.ask(args.agent, args.task, ticket_id=args.ticket[0] if args.ticket else None)
            print(out.model_dump_json(indent=2))
            return
        for ticket_id in args.ticket or await team.open_ticket_ids():
            print(f"\n=== Ticket {ticket_id}")
            try:
                print((await team.handle_ticket(ticket_id)).model_dump_json(indent=2))
            except Exception as exc:  # one ticket failing (e.g. its token budget ran out) doesn't stop the rest
                print(f"Ticket {ticket_id} stopped: {type(exc).__name__}: {exc}. See output/audit_trail.json.")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Run the Campus Customs agent team.")
    p.add_argument("--ticket", type=int, action="append", help="ticket id (repeatable); default: every open ticket")
    p.add_argument("--agent", choices=list(SPECS), help="start with this agent instead of the Boss (needs --task)")
    p.add_argument("--task", help="request for --agent")
    p.add_argument("--db", help="database file (default data/campus_customs_new.db)")
    args = p.parse_args()
    if bool(args.agent) != bool(args.task):
        p.error("--agent and --task go together")
    asyncio.run(main(args))
