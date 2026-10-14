// Who's who on the desk: each agent has its own color, glyph, and role line, so it's recognizable
// at a glance. The name always shows next to the color, so color is never the only cue.
import type { ReactElement } from "react";
import type { Actor } from "./api";

export interface Identity {
  name: string;
  role: string;
  color: string;     // identity color (never used for status)
  tint: string;      // soft background in light mode
  glyph: ReactElement;
}

const svg = (d: string) => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d={d} />
  </svg>
);

export const AGENTS: Record<Actor, Identity> = {
  boss: {
    name: "Boss", role: "Runs the desk, routes the work", color: "#6250d6", tint: "#ece9fb",
    glyph: svg("M12 2l2.6 6.2L21 9l-5 4.4L17.5 20 12 16.6 6.5 20 8 13.4 3 9l6.4-.8z"),
  },
  inventory: {
    name: "Inventory", role: "Stock, shortages, reorders", color: "#12936a", tint: "#e2f5ee",
    glyph: svg("M3 7.5 12 3l9 4.5v9L12 21l-9-4.5zM3 7.5 12 12l9-4.5M12 12v9"),
  },
  accounting: {
    name: "Accounting", role: "Cash, prices, payments", color: "#2a78d6", tint: "#e3eefb",
    glyph: svg("M4 4h16v16H4zM8 9h8M8 13h8M8 17h5"),
  },
  facilities: {
    name: "Facilities", role: "Lease and landlord", color: "#e0602c", tint: "#fdebe3",
    glyph: svg("M4 21V8l8-5 8 5v13M9 21v-6h6v6M8 11h.01M16 11h.01"),
  },
  customer_service: {
    name: "Customer Service", role: "Replies to customers", color: "#cf4a7d", tint: "#fbe7ef",
    glyph: svg("M4 5h16v11H9l-5 4zM8 9h8M8 12h5"),
  },
  team: {
    name: "Dashboard", role: "The backend", color: "#6b7280", tint: "#eef0f3",
    glyph: svg("M4 5h16v10H4zM9 19h6M12 15v4"),
  },
  human: {
    name: "You", role: "Approves money", color: "#9a6a00", tint: "#fbf1d6",
    glyph: svg("M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM4 21a8 8 0 0 1 16 0"),
  },
};

export const SPECIALISTS = ["inventory", "accounting", "facilities", "customer_service"] as const;

export function Avatar({ who, size = 34, active = false }: { who: Actor; size?: number; active?: boolean }) {
  const a = AGENTS[who] ?? AGENTS.team;
  return (
    <span
      className={`avatar${active ? " avatar--active" : ""}`}
      style={{ width: size, height: size, color: a.color, ["--agent" as string]: a.color, ["--tint" as string]: a.tint }}
      title={`${a.name}: ${a.role}`}
    >
      {a.glyph}
    </span>
  );
}

export function AgentTag({ who }: { who: Actor }) {
  const a = AGENTS[who] ?? AGENTS.team;
  return (
    <span className="agent-tag" style={{ ["--agent" as string]: a.color, ["--tint" as string]: a.tint }}>
      <Avatar who={who} size={20} />
      {a.name}
    </span>
  );
}
