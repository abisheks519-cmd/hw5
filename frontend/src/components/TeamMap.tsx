// The team as a little map: every agent can reach every other (faint lines = all 20 routes),
// and the hand-offs from the selected run light up as colored arrows in the asker's color.
import type { AgentEvent, AgentName } from "../api";
import { AGENTS, Avatar } from "../agents";

const POS: Record<AgentName, { x: number; y: number }> = {
  boss: { x: 50, y: 50 },
  inventory: { x: 12, y: 20 },
  accounting: { x: 88, y: 20 },
  facilities: { x: 88, y: 80 },
  customer_service: { x: 12, y: 80 },
};
const NAMES = Object.keys(POS) as AgentName[];

export function TeamMap({ events, running }: { events: AgentEvent[]; running: boolean }) {
  const edges = new Map<string, { from: AgentName; to: AgentName; count: number; last: number }>();
  const worked = new Set<string>();
  events.forEach((e) => {
    if (e.action === "run_start") worked.add(e.agent);
    if (e.action === "delegate" && e.tool?.startsWith("ask_")) {
      const from = e.agent as AgentName, to = e.tool.slice(4) as AgentName, key = `${from}>${to}`;
      const cur = edges.get(key);
      edges.set(key, { from, to, count: (cur?.count ?? 0) + 1, last: e.id });
    }
  });
  const lastAgentEvent = [...events].reverse().find((e) => e.agent in POS);
  const active = running ? (lastAgentEvent?.agent as AgentName | undefined) : undefined;
  const newest = Math.max(-1, ...[...edges.values()].map((e) => e.last));

  return (
    <div className="team-map" aria-label="Team map: who handed work to whom">
      <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="team-map__lines">
        <defs>
          {NAMES.map((n) => (
            <marker key={n} id={`arrow-${n}`} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
              <path d="M0 0 10 5 0 10z" fill={AGENTS[n].color} />
            </marker>
          ))}
        </defs>
        {NAMES.flatMap((a, i) => NAMES.slice(i + 1).map((b) => (
          <line key={`${a}-${b}`} x1={POS[a].x} y1={POS[a].y} x2={POS[b].x} y2={POS[b].y} className="team-map__route" />
        )))}
        {[...edges.values()].map(({ from, to, last }) => {
          const a = POS[from], b = POS[to];
          const dx = b.x - a.x, dy = b.y - a.y, len = Math.hypot(dx, dy) || 1;
          const ox = (-dy / len) * 1.6, oy = (dx / len) * 1.6;            // nudge so A→B and B→A don't overlap
          const shrink = 11 / len;                                        // stop short of the avatars
          return (
            <line
              key={`${from}>${to}`}
              x1={a.x + dx * shrink + ox} y1={a.y + dy * shrink + oy}
              x2={b.x - dx * shrink + ox} y2={b.y - dy * shrink + oy}
              stroke={AGENTS[from].color}
              markerEnd={`url(#arrow-${from})`}
              className={`team-map__edge${running && last === newest ? " team-map__edge--live" : ""}`}
            />
          );
        })}
      </svg>
      {NAMES.map((n) => (
        <div key={n} className={`team-map__node${worked.has(n) ? " team-map__node--worked" : ""}${POS[n].y < 50 ? " team-map__node--top" : ""}`} style={{ left: `${POS[n].x}%`, top: `${POS[n].y}%` }}>
          <Avatar who={n} size={44} active={active === n} />
          <span className="team-map__name" style={{ color: AGENTS[n].color }}>{AGENTS[n].name}</span>
        </div>
      ))}
      <div className="team-map__legend">
        {edges.size === 0 ? "Faint lines: every agent can hand work to every other." :
          [...edges.values()].map((e) => `${AGENTS[e.from].name} → ${AGENTS[e.to].name}${e.count > 1 ? ` ×${e.count}` : ""}`).join(" · ")}
      </div>
    </div>
  );
}
