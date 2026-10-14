// The live feed: what each agent said and did, in order, read straight from the backend's audit trail.
import { useEffect, useRef, useState } from "react";
import type { AgentEvent } from "../api";
import { AGENTS, AgentTag, Avatar } from "../agents";

const time = (ts: string) => new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
const name = (who: string) => AGENTS[who as keyof typeof AGENTS]?.name ?? who;

function args(v: unknown) {
  if (!v || typeof v !== "object") return "";
  return Object.entries(v as Record<string, unknown>).map(([k, x]) => `${k}: ${typeof x === "string" ? x : JSON.stringify(x)}`).join(" · ");
}

function isNoise(e: AgentEvent) {
  return e.action === "model_response" && !((e.result as { text?: string } | null)?.text);
}

function Body({ e }: { e: AgentEvent }) {
  const target = e.tool?.startsWith("ask_") ? e.tool.slice(4) : null;
  const result = e.result as Record<string, unknown> | null;
  switch (e.action) {
    case "run_start":
      return (
        <p className="feed__muted">
          {e.chain.length > 1 ? <>Picked up a hand-off from <strong>{name(e.chain[e.chain.length - 2])}</strong>: </> : "Started: "}
          {String((e.inputs as { task?: string } | null)?.task ?? "")}
        </p>
      );
    case "model_response":
      return <p className="bubble">{String(result?.text ?? "")}</p>;
    case "tool_call":
      return (
        <p className="tool-line">
          <span className="tool-chip">⚙ {e.tool}</span>
          <span className="tool-args">{args(e.inputs)}</span>
        </p>
      );
    case "tool_result":
      return (
        <details className="tool-result">
          <summary><span className="tool-chip tool-chip--result">↩ {e.tool}</span> returned data</summary>
          <pre>{typeof e.result === "string" ? e.result : JSON.stringify(e.result, null, 2)}</pre>
        </details>
      );
    case "tool_error":
      return <p className="feed__error"><span className="tool-chip tool-chip--error">✕ {e.tool}</span> {e.error}</p>;
    case "delegate":
      return (
        <div className="handoff">
          <span className="handoff__route"><AgentTag who={e.agent} /> <span aria-hidden="true">→</span> {target && <AgentTag who={target as AgentName} />}</span>
          <p>{String((e.inputs as { request?: string } | null)?.request ?? "")}</p>
        </div>
      );
    case "delegate_result":
      return <p className="feed__muted"><strong>{target && name(target)}</strong> reported back: {String(result?.summary ?? "")}</p>;
    case "delegate_refused":
      return <p className="feed__warn">Hand-off refused: {e.error}</p>;
    case "run_end":
      return <p className="bubble bubble--final"><strong>Done.</strong> {String(result?.summary ?? "")}</p>;
    case "approval":
      return <p className="bubble bubble--human">Approved transaction {String((e.inputs as { transaction_id?: number } | null)?.transaction_id)}: {String(result?.effect ?? "")}</p>;
    case "error":
      return <p className="feed__error">Stopped: {e.error}</p>;
    default:
      return <p className="feed__muted">{e.message}</p>;
  }
}

type AgentName = keyof typeof AGENTS;

export function ActivityFeed({ events, loading, error, running }: { events: AgentEvent[]; loading: boolean; error: string | null; running: boolean }) {
  const [showAll, setShowAll] = useState(false);
  const box = useRef<HTMLOListElement>(null);
  const shown = showAll ? events : events.filter((e) => !isNoise(e));

  useEffect(() => {  // follow the newest event while a run is going, unless you've scrolled up to read
    const el = box.current;
    if (el && running && el.scrollHeight - el.scrollTop - el.clientHeight < 160) el.scrollTop = el.scrollHeight;
  }, [shown.length, running]);

  return (
    <section className="panel feed" aria-label="Agent activity">
      <header className="panel__head">
        <h2>Activity</h2>
        <label className="toggle"><input type="checkbox" checked={showAll} onChange={(ev) => setShowAll(ev.target.checked)} /> every step</label>
      </header>
      {error && <p className="inline-error" role="alert">{error}</p>}
      {loading && events.length === 0 && [0, 1, 2, 3].map((i) => <div key={i} className="skeleton skeleton--event" />)}
      {!loading && !error && events.length === 0 && (
        <div className="empty">
          <p><strong>No activity yet.</strong></p>
          <p>Start the agent team and every message, hand-off, and tool call shows up here as it happens.</p>
        </div>
      )}
      <ol className="feed__list" ref={box} aria-live="polite">
        {shown.map((e) => (
          <li key={e.id} className={`feed__item feed__item--${e.action}`} style={{ ["--agent" as string]: AGENTS[e.agent]?.color ?? "#6b7280" }}>
            <Avatar who={e.agent} size={30} />
            <div className="feed__content">
              <div className="feed__meta">
                <strong style={{ color: AGENTS[e.agent]?.color }}>{name(e.agent)}</strong>
                <span className="muted">{time(e.ts)}</span>
              </div>
              <Body e={e} />
            </div>
          </li>
        ))}
        {running && (
          <li className="feed__item feed__item--typing">
            <span className="typing" aria-label="Agents are working"><i /><i /><i /></span>
          </li>
        )}
      </ol>
    </section>
  );
}
