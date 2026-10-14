"""Boss: takes each ticket, hands the work to the right teammates, and records the outcome."""

from backend.agents.base import AgentSpec
from backend.models import TicketOutcome

SPEC = AgentSpec(
    name="boss",
    title="Boss",
    role="runs the shop: reads tickets, assigns work, combines the answers, and records each ticket's status",
    model="gpt-6-luna",
    reasoning_effort="medium",
    prompt_file="boss.md",
    mcp_tools=frozenset({"list_open_tickets", "get_ticket", "update_ticket"}),
    output_type=TicketOutcome,
)
