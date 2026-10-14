"""Accounting: cash, bills, prices, discounts, and (with a person's approval) payments."""

from backend.agents.base import AgentSpec
from backend.models import SpecialistReport

SPEC = AgentSpec(
    name="accounting",
    title="Accounting",
    role="knows cash on hand, open invoices, rent owed, costs and prices, checks discounts, and prepares payments for a person to approve",
    model="gpt-6-luna",
    reasoning_effort="low",
    prompt_file="accounting.md",
    mcp_tools=frozenset({"get_ticket", "get_cash_position", "get_invoice", "get_rent_due", "get_pricing",
                         "check_discount", "prepare_payment"}),
    output_type=SpecialistReport,
)
