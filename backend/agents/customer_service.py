"""Customer Service: drafts replies to customers and groups. Drafts only; a person sends them."""

from backend.agents.base import AgentSpec
from backend.models import SpecialistReport

SPEC = AgentSpec(
    name="customer_service",
    title="Customer Service",
    role="drafts replies to customers and student groups using only checked facts (drafts only, never sent)",
    model="gpt-6-luna",
    reasoning_effort="low",
    prompt_file="customer_service.md",
    mcp_tools=frozenset({"get_ticket", "check_inventory", "get_pricing"}),
    output_type=SpecialistReport,
)
