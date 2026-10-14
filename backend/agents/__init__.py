"""The Campus Customs agent team: one file per agent."""

from backend.agents import accounting, boss, customer_service, facilities, inventory
from backend.agents.base import AgentSpec
from backend.models import AgentName

SPECS: dict[AgentName, AgentSpec] = {
    m.SPEC.name: m.SPEC for m in (boss, inventory, accounting, facilities, customer_service)
}
