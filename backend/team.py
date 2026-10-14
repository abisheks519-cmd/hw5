"""The Campus Customs agent team: five PydanticAI agents, fully connected, all using MCP for data.

- Data: every agent gets a filtered view of ONE campus-customs MCP connection, so it can only
  call the MCP tools listed in its spec. There are no other data tools.
- Money: the agents' MCP connection has no approval tool. Agents can only PREPARE payments and
  purchases; a person approves them through the FastAPI backend (backend/main.py).
- Delegation: every agent has an ask_<name> tool for each of the other four agents (full
  connectivity). A hand-off is refused if it would loop back to an agent already working on the
  request, or make the chain longer than TeamLimits.max_chain.
- Loop: run_agent() steps through PydanticAI's agent loop with agent.iter() and appends every
  step (model request, model response, tool call, tool result, hand-off, error, final output)
  to output/audit_trail.json.
- Limits: every agent working on one ticket shares one RunUsage, so TeamLimits caps the whole
  ticket (requests, tool calls, tokens), not each agent separately.
"""

from __future__ import annotations

import os
from typing import Any
from uuid import uuid4

from pydantic_ai import Agent, RunContext
from pydantic_ai.messages import (
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    RetryPromptPart,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.models import Model
from pydantic_ai.tools import Tool
from pydantic_ai.toolsets import FunctionToolset
from pydantic_ai.usage import RunUsage

from backend.agents import SPECS
from backend.agents.base import AgentSpec, build_instructions
from backend.audit import AuditTrail
from backend.llm import gateway_model
from backend.mcp_connection import campus_customs_toolset
from backend.models import AgentName, AuditRecord, TeamDeps, TeamLimits, TicketOutcome

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")  # the console banner would mix into the run output


def new_run_id() -> str:
    return f"run-{uuid4().hex[:12]}"


def usage_summary(usage: RunUsage) -> dict[str, int]:
    return {"requests": usage.requests, "tool_calls": usage.tool_calls,
            "input_tokens": usage.input_tokens, "output_tokens": usage.output_tokens}


def describe_part(part: Any) -> dict[str, Any]:
    """What one piece of a model request is, without repeating whole tool results (those are logged as tool_result)."""
    if isinstance(part, UserPromptPart):
        return {"user_prompt": part.content}
    if isinstance(part, ToolReturnPart):
        return {"tool_return": part.tool_name}
    if isinstance(part, RetryPromptPart):
        return {"retry": part.tool_name, "message": part.model_response()}
    return {"part": part.part_kind}


class Team:
    def __init__(self, *, db_path: str | None = None,
                 limits: TeamLimits | None = None, audit: AuditTrail | None = None,
                 model_factory: Any = None):
        """model_factory(spec) -> Model replaces the gateway models (used by the scripted tests)."""
        self.limits = limits or TeamLimits()
        self.audit = audit or AuditTrail()
        self.database = str(db_path or "data/campus_customs_new.db")
        self.mcp = campus_customs_toolset(db_path)  # the agents' connection: no approval tool, so no agent can move money
        self.model_names: dict[AgentName, str] = {}
        self.agents: dict[AgentName, Agent[TeamDeps, Any]] = {}
        for name, spec in SPECS.items():
            model = model_factory(spec) if model_factory else gateway_model(spec.model)
            self.model_names[name] = model.model_name
            self.agents[name] = self._build_agent(spec, model)

    async def __aenter__(self) -> Team:
        await self.mcp.__aenter__()  # one MCP server process for the whole session
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.mcp.__aexit__(*exc)

    # ------------------------------------------------------------ building the agents

    def _build_agent(self, spec: AgentSpec, model: Model) -> Agent[TeamDeps, Any]:
        allowed = spec.mcp_tools
        mcp_view = self.mcp.filtered(lambda ctx, tool_def: tool_def.name in allowed)
        asks = FunctionToolset([self._ask_tool(spec.name, other) for other in SPECS if other != spec.name])
        return Agent(
            model,
            name=spec.name,
            deps_type=TeamDeps,
            output_type=spec.output_type,
            instructions=build_instructions(spec, SPECS),
            toolsets=[mcp_view, asks],
            retries=self.limits.output_retries,
            model_settings={"max_tokens": self.limits.max_output_tokens, "openai_reasoning_effort": spec.reasoning_effort},
        )

    def _ask_tool(self, caller: AgentName, target: AgentName) -> Tool[TeamDeps]:
        spec = SPECS[target]

        async def ask(ctx: RunContext[TeamDeps], request: str) -> dict[str, Any]:
            """Hand part of the work to a teammate and get their report back.

            Args:
                request: The ticket id, what you already know, and one clear question for this teammate.
            """
            return await self.delegate(ctx, caller, target, request)

        return Tool(ask, takes_ctx=True, name=f"ask_{target}",
                    description=f"Ask {spec.title}, who {spec.role}. Returns their report.")

    # ------------------------------------------------------------ delegation

    async def delegate(self, ctx: RunContext[TeamDeps], caller: AgentName, target: AgentName, request: str) -> dict[str, Any]:
        deps, chain = ctx.deps, ctx.deps.chain
        if target in chain:
            refusal = (f"{SPECS[target].title} is already working on this request ({' -> '.join(chain)}). "
                       "Answer with what you have, or ask a different teammate.")
        elif len(chain) >= self.limits.max_chain:
            refusal = (f"The hand-off chain {' -> '.join(chain)} is already {len(chain)} agents long, the limit. "
                       "Answer with what you have.")
        else:
            sub = TeamDeps(team=self, run_id=deps.run_id, ticket_id=deps.ticket_id, chain=(*chain, target))
            report = await self.run_agent(target, request, sub, usage=ctx.usage)
            return report.model_dump()
        self.log(deps, caller, "delegate_refused", ctx.run_step, tool=f"ask_{target}", inputs={"request": request}, error=refusal)
        return {"refused": refusal}

    # ------------------------------------------------------------ the agent loop

    def log(self, deps: TeamDeps, agent: AgentName | str, action: str, step: int = 0, **fields: Any) -> None:
        self.audit.append(AuditRecord(run_id=deps.run_id, ticket_id=deps.ticket_id, agent=agent, chain=list(deps.chain),
                                      step=step, action=action, **fields))

    async def run_agent(self, name: AgentName, task: str, deps: TeamDeps, usage: RunUsage) -> Any:
        """Run one agent to its final output, logging every step of its loop."""
        agent, step = self.agents[name], 0
        self.log(deps, name, "run_start", inputs={"task": task},
                 detail={"model": self.model_names[name], "database": self.database, "limits": self.limits.model_dump()})
        try:
            async with agent.iter(task, deps=deps, usage=usage, usage_limits=self.limits.usage_limits()) as run:
                async for node in run:
                    if Agent.is_model_request_node(node):
                        step += 1
                        self.log(deps, name, "model_request", step, inputs=[describe_part(p) for p in node.request.parts])
                    elif Agent.is_call_tools_node(node):
                        response = node.model_response
                        self.log(deps, name, "model_response", step,
                                 result={"text": "".join(p.content for p in response.parts if isinstance(p, TextPart)) or None,
                                         "tool_calls": [{"tool": p.tool_name, "args": p.args_as_dict()}
                                                        for p in response.parts if isinstance(p, ToolCallPart)]},
                                 detail={"model": response.model_name, "stop_reason": response.finish_reason,
                                         "input_tokens": response.usage.input_tokens, "output_tokens": response.usage.output_tokens})
                        async with node.stream(run.ctx) as events:
                            async for event in events:
                                if isinstance(event, FunctionToolCallEvent):
                                    tool = event.part.tool_name
                                    self.log(deps, name, "delegate" if tool.startswith("ask_") else "tool_call", step,
                                             tool=tool, inputs=event.part.args_as_dict())
                                elif isinstance(event, FunctionToolResultEvent):
                                    self._log_tool_result(deps, name, step, event)
                output = run.result.output
        except Exception as exc:
            self.log(deps, name, "error", step, error=f"{type(exc).__name__}: {exc}",
                     detail={"ticket_usage_so_far": usage_summary(usage)})
            raise
        self.log(deps, name, "run_end", step, result=output.model_dump(), detail={"ticket_usage_so_far": usage_summary(usage)})
        return output

    def _log_tool_result(self, deps: TeamDeps, name: AgentName, step: int, event: FunctionToolResultEvent) -> None:
        part = event.part
        if isinstance(part, RetryPromptPart):
            self.log(deps, name, "tool_error", step, tool=part.tool_name, error=part.model_response())
        elif getattr(part, "outcome", "success") != "success":
            self.log(deps, name, "tool_error", step, tool=part.tool_name, error=str(part.content),
                     detail={"outcome": part.outcome})
        else:
            action = "delegate_result" if part.tool_name.startswith("ask_") else "tool_result"
            self.log(deps, name, action, step, tool=part.tool_name, result=part.content)

    # ------------------------------------------------------------ entry points

    async def handle_ticket(self, ticket_id: int, run_id: str | None = None) -> TicketOutcome:
        """The Boss works one ticket, with its own token budget."""
        deps = TeamDeps(team=self, run_id=run_id or new_run_id(), ticket_id=ticket_id, chain=("boss",))
        task = (f"Handle ticket {ticket_id}. Read it with get_ticket, ask the teammates whose tools cover it, "
                "record the result with update_ticket (author 'boss'), then return the TicketOutcome.")
        return await self.run_agent("boss", task, deps, usage=RunUsage())

    async def ask(self, agent: AgentName, task: str, ticket_id: int | None = None) -> Any:
        """Start with any agent, not just the Boss."""
        deps = TeamDeps(team=self, run_id=new_run_id(), ticket_id=ticket_id, chain=(agent,))
        return await self.run_agent(agent, task, deps, usage=RunUsage())

    async def open_ticket_ids(self) -> list[int]:
        """Ask the MCP server which tickets are open (logged like any other tool call)."""
        deps = TeamDeps(team=self, run_id=f"dispatch-{uuid4().hex[:12]}", ticket_id=None, chain=())
        self.log(deps, "team", "tool_call", tool="list_open_tickets", inputs={})
        result = await self.mcp.direct_call_tool("list_open_tickets", {})
        ids = [t["id"] for t in result["tickets"]]
        self.log(deps, "team", "tool_result", tool="list_open_tickets", result={"shop_date": result["shop_date"], "open_ticket_ids": ids})
        return ids
