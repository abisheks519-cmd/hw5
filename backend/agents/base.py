"""What defines an agent, and how its instructions are put together.

Every agent's instructions are three prompt files from backend/prompts/, in this order:
team_rules.md (rules for all agents), shop_rules.md (the shop's policies, written by the
owner), then the agent's own file. A generated "Your teammates" list goes at the end, so
every agent knows who it can ask.
"""

import re
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel

from backend.models import AgentName

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
NO_SHOP_RULES = (
    "# Shop rules\n\nThe owner has not written the shop rules yet. When a decision depends on a shop policy "
    "(how big a discount can be, which bill to pay first, what to promise a customer), do not invent a rule: "
    "add it to approvals_needed so the owner decides."
)


@dataclass(frozen=True)
class AgentSpec:
    name: AgentName
    title: str               # display name, e.g. "Customer Service"
    role: str                # one line; also used to describe the ask_<name> tool to teammates
    model: str               # must be gpt-6-luna (checked in backend/llm.py)
    reasoning_effort: str    # "low" keeps token use down; the Boss plans, so it gets more
    prompt_file: str         # file in backend/prompts/
    mcp_tools: frozenset[str]  # campus-customs tools this agent may call; it never sees the others
    output_type: type[BaseModel]


def read_prompt(name: str) -> str:
    """A prompt file with its <!-- comments --> removed (comments are notes for the person editing it)."""
    text = (PROMPTS_DIR / name).read_text()
    return re.sub(r"<!--.*?-->", "", text, flags=re.S).strip()


def build_instructions(spec: AgentSpec, specs: dict[str, AgentSpec]) -> str:
    shop_rules = read_prompt("shop_rules.md")
    shop_rules = shop_rules if re.sub(r"^#.*$", "", shop_rules, flags=re.M).strip() else NO_SHOP_RULES
    teammates = "\n".join(f"- `ask_{s.name}`: {s.title}, {s.role}" for s in specs.values() if s.name != spec.name)
    tools = ", ".join(f"`{t}`" for t in sorted(spec.mcp_tools))
    return "\n\n".join([
        read_prompt("team_rules.md"),
        shop_rules,
        read_prompt(spec.prompt_file),
        f"# Your tools\n\ncampus-customs MCP tools: {tools}.\n\n# Your teammates\n\nYou can ask any of them:\n{teammates}",
    ])
