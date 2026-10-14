// The money desk: the checking balance, a cash log you can add up, and the approval queue.
// Agents only prepare transactions; the Approve button here is the only thing that moves cash.
import { useEffect, useRef, useState } from "react";
import type { Cash, Transaction } from "../api";
import { money } from "../api";
import { AGENTS, Avatar } from "../agents";

const KIND: Record<Transaction["kind"], string> = { rent: "Rent", invoice: "Vendor invoice", purchase: "Reorder" };

function CashTile({ cash, approved, error }: { cash: Cash | null; approved: Transaction[]; error: string | null }) {
  const [flash, setFlash] = useState(false);
  const prev = useRef<number | null>(null);
  useEffect(() => {
    if (cash && prev.current !== null && cash.balance !== prev.current) {
      setFlash(true);
      const t = setTimeout(() => setFlash(false), 1600);
      prev.current = cash.balance;
      return () => clearTimeout(t);
    }
    if (cash) prev.current = cash.balance;
  }, [cash]);
  const spent = approved.reduce((s, t) => s + t.amount, 0);
  return (
    <div className={`cash-tile${flash ? " cash-tile--flash" : ""}`}>
      <p className="cash-tile__label">Checking balance</p>
      {error && <p className="inline-error" role="alert">{error}</p>}
      {!cash && !error && <div className="skeleton skeleton--number" />}
      {cash && (
        <>
          <p className="cash-tile__value">{money(cash.balance)}</p>
          <p className="cash-tile__sub">
            {spent > 0 ? <span className="delta delta--down">▼ {money(spent)} approved since reset</span> : <span className="muted">No payments since reset</span>}
            <span className="muted"> · as of {cash.as_of}</span>
          </p>
        </>
      )}
    </div>
  );
}

function CashLog({ cash, approved }: { cash: Cash; approved: Transaction[] }) {
  const ordered = [...approved].sort((a, b) => (a.payment_id ?? 0) - (b.payment_id ?? 0));
  const start = cash.balance + ordered.reduce((s, t) => s + t.amount, 0);
  let running = start;
  return (
    <table className="cash-log">
      <caption>Cash log since reset</caption>
      <tbody>
        <tr><th scope="row">Starting balance</th><td className="num">{money(start)}</td></tr>
        {ordered.map((t) => {
          running -= t.amount;
          return (
            <tr key={t.id}>
              <th scope="row">#{t.id} {KIND[t.kind]} · ticket {t.ticket_id ?? "—"}</th>
              <td className="num"><span className="delta delta--down">−{money(t.amount)}</span><br /><span className="muted">{money(running)}</span></td>
            </tr>
          );
        })}
        <tr className="cash-log__total"><th scope="row">Now</th><td className="num">{money(cash.balance)}</td></tr>
      </tbody>
    </table>
  );
}

export function MoneyDesk({ cash, cashError, txns, txnError, approver, setApprover, approving, onApprove }: {
  cash: Cash | null; cashError: string | null; txns: Transaction[] | null; txnError: string | null;
  approver: string; setApprover: (v: string) => void; approving: Set<number>; onApprove: (t: Transaction) => void;
}) {
  const pending = txns?.filter((t) => t.status === "pending") ?? [];
  const approved = txns?.filter((t) => t.status === "approved") ?? [];
  const nameOk = approver.trim().length > 0;
  return (
    <aside className="panel money" aria-label="Money desk">
      <header className="panel__head"><h2>Money desk</h2></header>
      <CashTile cash={cash} approved={approved} error={cashError} />

      <div className="approvals">
        <div className="approvals__head">
          <h3>Waiting for your approval</h3>
          {pending.length > 0 && <span className="count-badge">{pending.length}</span>}
        </div>
        <label className="approver">
          <span>Approving as</span>
          <input value={approver} onChange={(e) => setApprover(e.target.value)} placeholder="Your name" maxLength={80} />
        </label>
        {txnError && <p className="inline-error" role="alert">{txnError}</p>}
        {!txns && !txnError && <div className="skeleton skeleton--card" />}
        {txns && pending.length === 0 && (
          <p className="empty empty--small">Nothing to approve. When an agent prepares a payment or a reorder, it lands here. No money moves until you click Approve.</p>
        )}
        {pending.map((t) => {
          const busy = approving.has(t.id);
          const after = cash ? cash.balance - t.amount : null;
          return (
            <article key={t.id} className={`approval approval--${t.kind}`}>
              <div className="approval__top">
                <span className="approval__kind">{KIND[t.kind]} · #{t.id}</span>
                <span className="approval__amount">{money(t.amount)}</span>
              </div>
              <p className="approval__desc">{t.description}</p>
              <p className="approval__meta">
                <Avatar who={t.prepared_by} size={18} /> prepared by {AGENTS[t.prepared_by].name}{t.ticket_id ? ` for ticket ${t.ticket_id}` : ""}
              </p>
              {after !== null && (
                <p className={`approval__after${after < 500 ? " approval__after--low" : ""}`}>
                  Checking after approval: <strong>{money(after)}</strong>{after < 0 ? " (not enough cash)" : after < 500 ? " (under the $500 warning line)" : ""}
                </p>
              )}
              <button className="btn btn--approve" disabled={busy || !nameOk || (after !== null && after < 0)} onClick={() => onApprove(t)}>
                {busy ? <><span className="spinner spinner--light" /> Approving…</> : <>Approve {money(t.amount)}</>}
              </button>
              {!nameOk && <p className="hint">Type your name above to approve.</p>}
            </article>
          );
        })}
      </div>

      {cash && <CashLog cash={cash} approved={approved} />}

      {approved.length > 0 && (
        <details className="approved-list">
          <summary>Approved ({approved.length})</summary>
          <ul>
            {approved.map((t) => (
              <li key={t.id}>✓ #{t.id} {money(t.amount)} · {t.description} <span className="muted">by {t.approved_by}, payment {t.payment_id}</span></li>
            ))}
          </ul>
        </details>
      )}
    </aside>
  );
}
