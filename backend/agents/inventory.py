"""Inventory: stock on the shelf, shortages, and reorders from vendors."""

from backend.agents.base import AgentSpec
from backend.models import SpecialistReport

SPEC = AgentSpec(
    name="inventory",
    title="Inventory",
    role="knows stock by size and aisle, shortages, which vendor supplies what, reorder lead times, and prepares reorders for a person to approve",
    model="gpt-6-luna",
    reasoning_effort="low",
    prompt_file="inventory.md",
    mcp_tools=frozenset({"get_ticket", "check_inventory", "list_vendors", "get_invoice", "prepare_purchase"}),
    output_type=SpecialistReport,
)
