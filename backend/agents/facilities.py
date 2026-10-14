"""Facilities: the shop space, the lease, and the landlord."""

from backend.agents.base import AgentSpec
from backend.models import SpecialistReport

SPEC = AgentSpec(
    name="facilities",
    title="Facilities",
    role="looks after the shop space and its lease: rent amount, due dates, and dealings with the landlord",
    model="gpt-6-luna",
    reasoning_effort="low",
    prompt_file="facilities.md",
    mcp_tools=frozenset({"get_ticket", "get_rent_due"}),
    output_type=SpecialistReport,
)
