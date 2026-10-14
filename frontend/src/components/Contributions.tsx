// "Who did what" for the selected ticket's latest run, built from GET /api/runs/{run_id}.
import type { RunDetail } from "../api";
import { AGENTS, AgentTag, Avatar } from "../agents";

export function Contributions({ run, loading }: { run: RunDetail | null; loading: boolean }) {
  if (loading && !run) return <section className="panel"><div className="skeleton skeleton--card" /></section>;
  if (!run) return null;
  const cards = run.contributions;
  return (
    <section className="panel contributions" aria-label="Each agent's contribution">
      <header className="panel__head">
        <h2>Who did what</h2>
        <span className="muted">{cards.length} agent{cards.length === 1 ? "" : "s"} on this run{run.status === "running" ? " so far" : ""}</span>
      </header>
      {run.outcome && (
        <div className="outcome">
          <p className="outcome__label">Boss's wrap-up</p>
          <p>{run.outcome.summary}</p>
          {run.outcome.next_steps.length > 0 && (
            <ul className="outcome__steps">{run.outcome.next_steps.map((s, i) => <li key={i}>{s}</li>)}</ul>
          )}
        </div>
      )}
      {run.error && <p className="inline-error" role="alert">This run stopped: {run.error}</p>}
      <div className="contrib-grid">
        {cards.map((c) => (
          <article key={c.agent} className="contrib" style={{ ["--agent" as string]: AGENTS[c.agent].color, ["--tint" as string]: AGENTS[c.agent].tint }}>
            <header className="contrib__head">
              <Avatar who={c.agent} size={36} />
              <div>
                <h3>{AGENTS[c.agent].name}</h3>
                <p className="muted">
                  {c.asked_by.length ? <>asked by {c.asked_by.map((a) => AGENTS[a].name).join(", ")}</> : "started the run"}
                  {c.times_asked > 1 ? ` · asked ${c.times_asked}×` : ""}
                </p>
              </div>
            </header>
            <p className="contrib__summary">{c.summary ?? (run.status === "running" ? "Still working…" : "No summary.")}</p>
            {c.tools_used.length > 0 && (
              <div className="chips">{c.tools_used.map((t) => <span key={t.tool} className="tool-chip">⚙ {t.tool}{t.calls > 1 ? ` ×${t.calls}` : ""}</span>)}</div>
            )}
            {c.handed_off_to.length > 0 && (
              <p className="contrib__handoffs">Handed off to {[...new Set(c.handed_off_to)].map((a) => <AgentTag key={a} who={a} />)}</p>
            )}
            {c.actions_taken.length > 0 && (
              <ul className="contrib__list">{c.actions_taken.map((a, i) => <li key={i}>{a}</li>)}</ul>
            )}
            {c.reply_draft && (
              <figure className="draft">
                <figcaption>Reply draft · for a person to review and send</figcaption>
                <blockquote>{c.reply_draft}</blockquote>
              </figure>
            )}
            {c.errors.length > 0 && <p className="feed__warn">{c.errors.length} refused or failed step{c.errors.length > 1 ? "s" : ""}: {c.errors[0]}</p>}
          </article>
        ))}
      </div>
    </section>
  );
}
