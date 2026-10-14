import type { Ticket } from "../api";
import { StatusPill } from "./StatusPill";

const TYPE_LABEL: Record<string, string> = {
  customer_order: "Customer order",
  rent_notice: "Rent notice",
  price_override: "Discount request",
};

export function ticketPill(t: Ticket, runningTicket: number | null) {
  if (runningTicket === t.id) return <StatusPill kind="running" />;
  if (t.latest_run?.status === "failed" && t.state !== "resolved") return <StatusPill kind="failed" />;
  return t.state === "resolved" ? <StatusPill kind="resolved" /> : <StatusPill kind="open" label={t.status === "open" ? "Open" : `Open · ${t.status.replace(/_/g, " ")}`} />;
}

export function TicketList({ tickets, error, selected, runningTicket, onSelect }: {
  tickets: Ticket[] | null; error: string | null; selected: number | null; runningTicket: number | null; onSelect: (id: number) => void;
}) {
  const resolved = tickets?.filter((t) => t.state === "resolved").length ?? 0;
  return (
    <section className="panel queue" aria-label="Tickets">
      <header className="panel__head">
        <h2>Ticket queue</h2>
        {tickets && <span className="muted">{resolved} of {tickets.length} resolved</span>}
      </header>
      {tickets && (
        <div className="progress" aria-hidden="true">
          <span style={{ width: `${(resolved / Math.max(tickets.length, 1)) * 100}%` }} />
        </div>
      )}
      {error && <p className="inline-error" role="alert">{error}</p>}
      {!tickets && !error && [0, 1, 2].map((i) => <div key={i} className="skeleton skeleton--ticket" />)}
      <ul className="tickets">
        {tickets?.map((t) => (
          <li key={t.id}>
            <button
              className={`ticket-card${selected === t.id ? " ticket-card--selected" : ""}${t.state === "resolved" ? " ticket-card--resolved" : ""}`}
              onClick={() => onSelect(t.id)}
              aria-pressed={selected === t.id}
            >
              <span className="ticket-card__top">
                <span className="ticket-card__id">#{t.id}</span>
                {ticketPill(t, runningTicket)}
              </span>
              <span className="ticket-card__subject">{t.subject}</span>
              <span className="ticket-card__meta">{TYPE_LABEL[t.type] ?? t.type} · {t.requester}</span>
              {t.sku && <span className="ticket-card__item">{t.qty} × {t.sku}{t.size ? ` · size ${t.size}` : ""}</span>}
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
