"""Data types for the Campus Customs agent team.

Agents never hold shop data themselves: every fact in these types is copied from a
campus-customs MCP tool result (see mcp_server/server.py for the tool result types).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, Field
from pydantic_ai.usage import UsageLimits

if TYPE_CHECKING:
    from backend.team import Team

AgentName = Literal["boss", "inventory", "accounting", "facilities", "customer_service"]
TicketStatus = Literal["open", "in_progress", "waiting_on_stock", "waiting_on_approval", "resolved"]


# ---------------------------------------------------------------- what agents hand back

class Fact(BaseModel):
    """One shop fact an agent relied on, and the MCP tool it came from."""

    label: str = Field(description="What the value is, e.g. 'CC-TEE-WHITE size S on hand'")
    value: str = Field(description="The value exactly as the tool returned it, e.g. '0'")
    source_tool: str = Field(description="campus-customs tool that returned it, e.g. 'check_inventory'")


class ApprovalRequest(BaseModel):
    """Something only a person may decide: moving money, giving a discount, promising a customer."""

    action: str = Field(description="What should happen, e.g. 'Pay invoice 501 to Bulldog Print Co'")
    amount: float | None = Field(default=None, description="Dollars involved, if any")
    reason: str = Field(description="Why it is needed, citing tool values")


class SpecialistReport(BaseModel):
    """What Inventory, Accounting, Facilities, or Customer Service returns to the teammate who asked."""

    summary: str = Field(description="Two or three sentences that answer the request")
    facts: list[Fact] = Field(default_factory=list, description="Every shop value the summary relies on")
    actions_taken: list[str] = Field(default_factory=list, description="Changes made with MCP write tools; empty if none")
    approvals_needed: list[ApprovalRequest] = Field(default_factory=list)
    reply_draft: str | None = Field(default=None, description="Draft message to the requester. Never sent automatically.")
    open_questions: list[str] = Field(default_factory=list, description="Anything the tools could not answer")


class TicketOutcome(BaseModel):
    """The Boss's final result for one ticket."""

    ticket_id: int
    status: TicketStatus = Field(description="The status the Boss set with update_ticket")
    summary: str = Field(description="Two or three sentences: what was found and what happens next")
    delegated_to: list[AgentName] = Field(default_factory=list, description="Teammates the Boss asked")
    facts: list[Fact] = Field(default_factory=list)
    approvals_needed: list[ApprovalRequest] = Field(default_factory=list)
    reply_draft: str | None = Field(default=None, description="Draft reply to the requester, for a person to review and send")
    next_steps: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------- run settings

class TeamLimits(BaseModel):
    """Token-use and loop limits. One budget is shared by every agent working on the same ticket."""

    request_limit: int = Field(30, description="Model requests per ticket, all agents together")
    tool_calls_limit: int = Field(40, description="Tool calls (MCP and ask_*) per ticket, all agents together")
    total_tokens_limit: int = Field(300_000, description="Input + output tokens per ticket, all agents together")
    max_output_tokens: int = Field(4_000, description="Output tokens per model response")
    max_chain: int = Field(3, description="Longest delegation chain, e.g. boss -> facilities -> accounting")
    output_retries: int = Field(2, description="Times an agent may fix a final answer that fails validation")

    def usage_limits(self) -> UsageLimits:
        return UsageLimits(request_limit=self.request_limit, tool_calls_limit=self.tool_calls_limit,
                           total_tokens_limit=self.total_tokens_limit)


@dataclass
class TeamDeps:
    """PydanticAI deps passed to every agent run."""

    team: Team
    run_id: str  # one id per ticket run, shared by every agent working on it
    ticket_id: int | None
    chain: tuple[AgentName, ...]  # who is working right now, outermost first: ("boss", "facilities")


# ---------------------------------------------------------------- audit trail

AuditAction = Literal[
    "run_start",         # an agent starts working on a task
    "model_request",     # the loop sends the prompt or tool results to the model
    "model_response",    # the model answers: text and/or the tools it wants to call
    "tool_call",         # an MCP tool is called (with its inputs)
    "tool_result",       # an MCP tool returns
    "tool_error",        # an MCP tool refuses or fails
    "delegate",          # an agent asks a teammate (ask_*)
    "delegate_result",   # the teammate's report comes back
    "delegate_refused",  # the ask would loop back or go past max_chain
    "run_end",           # an agent finishes, with its final output
    "error",             # the run stopped: model error, limit reached, ...
    "approval",          # a person approved a prepared payment or purchase (dashboard)
    "reset",             # a person reset the database to its original values (dashboard)
]


class AuditRecord(BaseModel):
    """One line of output/audit_trail.json."""

    ts: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="milliseconds"))
    run_id: str
    ticket_id: int | None
    agent: AgentName | Literal["team", "human"]
    chain: list[str] = Field(description="Delegation chain at this step, outermost first")
    step: int = Field(description="Model request number within this agent's run (0 before the first request)")
    action: AuditAction
    tool: str | None = None
    inputs: Any = None
    result: Any = None
    error: str | None = None
    detail: dict[str, Any] | None = Field(default=None, description="Model name, tokens, stop reason, limits, ...")
