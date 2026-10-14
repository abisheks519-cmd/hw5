import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { AgentEvent, Cash, Health, RunDetail, RunInfo, Ticket, Transaction } from "./api";
import { ApiError, api, money } from "./api";
import { AGENTS, Avatar, SPECIALISTS } from "./agents";
import { TicketList, ticketPill } from "./components/TicketList";
import { TeamMap } from "./components/TeamMap";
import { ActivityFeed } from "./components/ActivityFeed";
import { Contributions } from "./components/Contributions";
import { MoneyDesk } from "./components/MoneyDesk";

type Toast = { id: number; kind: "info" | "success" | "warn" | "error"; text: string };
const errText = (e: unknown) => (e instanceof Error ? e.message : String(e));
const BOARD_POLL_MS = 5000;
const RUN_POLL_MS = 1200;

function mergeEvents(prev: AgentEvent[] = [], next: AgentEvent[]) {
  const seen = new Set(prev.map((e) => e.id));
  return [...prev, ...next.filter((e) => !seen.has(e.id))].sort((a, b) => a.id - b.id);
}

export default function App() {
  // ---- board data (live from the backend)
  const [tickets, setTickets] = useState<Ticket[] | null>(null);
  const [shopDate, setShopDate] = useState<string | null>(null);
  const [ticketsError, setTicketsError] = useState<string | null>(null);
  const [txns, setTxns] = useState<Transaction[] | null>(null);
  const [txnError, setTxnError] = useState<string | null>(null);
  const [cash, setCash] = useState<Cash | null>(null);
  const [cashError, setCashError] = useState<string | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [offline, setOffline] = useState<string | null>(null);

  // ---- runs
  const [selected, setSelected] = useState<number | null>(null);
  const [activeRun, setActiveRun] = useState<RunInfo | null>(null);
  const [starting, setStarting] = useState(false);
  const [viewRunId, setViewRunId] = useState<string | null>(null);
  const [eventsByRun, setEventsByRun] = useState<Record<string, AgentEvent[]>>({});
  const [runDetails, setRunDetails] = useState<Record<string, RunDetail>>({});
  const [feedLoading, setFeedLoading] = useState(false);
  const [feedError, setFeedError] = useState<string | null>(null);

  // ---- approvals and reset
  const [approver, setApprover] = useState(() => localStorage.getItem("cc.approver") ?? "");
  const [approving, setApproving] = useState<Set<number>>(new Set());
  const [resetArmed, setResetArmed] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const toastId = useRef(0);

  const toast = useCallback((kind: Toast["kind"], text: string) => {
    const id = ++toastId.current;
    setToasts((t) => [...t, { id, kind, text }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), kind === "error" ? 9000 : 6000);
  }, []);

  useEffect(() => localStorage.setItem("cc.approver", approver), [approver]);

  const refreshBoard = useCallback(async () => {
    const [t, x, c] = await Promise.allSettled([api.tickets(), api.transactions("all"), api.cash()]);
    const down = [t, x, c].find((r) => r.status === "rejected" && r.reason instanceof ApiError && r.reason.status === 0);
    setOffline(down && down.status === "rejected" ? errText(down.reason) : null);
    if (t.status === "fulfilled") { setTickets(t.value.tickets); setShopDate(t.value.shop_date); setTicketsError(null); }
    else setTicketsError(errText(t.reason));
    if (x.status === "fulfilled") { setTxns(x.value.transactions); setTxnError(null); } else setTxnError(errText(x.reason));
    if (c.status === "fulfilled") { setCash(c.value); setCashError(null); } else setCashError(errText(c.reason));
    return t.status === "fulfilled" ? t.value.tickets : null;
  }, []);

  // Live board: load now, then keep it fresh.
  useEffect(() => {
    refreshBoard();
    const h = setInterval(refreshBoard, BOARD_POLL_MS);
    return () => clearInterval(h);
  }, [refreshBoard]);
  useEffect(() => {
    const check = () => api.health().then(setHealth).catch(() => setHealth(null));
    check();
    const h = setInterval(check, 10000);
    return () => clearInterval(h);
  }, []);

  // Pick a ticket once they load, and pick up a run that's already going (e.g. after a page reload).
  useEffect(() => {
    if (!tickets) return;
    if (selected === null) setSelected((tickets.find((t) => t.state === "open") ?? tickets[0])?.id ?? null);
    const running = tickets.find((t) => t.latest_run?.status === "running")?.latest_run;
    if (running && !activeRun) setActiveRun(running);
  }, [tickets, selected, activeRun]);

  const ticket = tickets?.find((t) => t.id === selected) ?? null;
  const latestRunId = ticket?.latest_run?.run_id ?? null;

  // Which run the feed shows for the selected ticket.
  useEffect(() => {
    if (selected === null || !ticket) return;
    if (activeRun?.ticket_id === selected) { setViewRunId(activeRun.run_id); return; }
    if (latestRunId) { setViewRunId(latestRunId); return; }
    if (ticket.state !== "resolved") { setViewRunId(null); return; }  // fresh after a reset: nothing to show
    let cancelled = false;  // resolved before this page (or the server) started: find its run in the audit trail
    api.events({ ticket_id: selected, limit: 500 })
      .then((r) => { if (!cancelled) setViewRunId([...r.events].reverse().find((e) => e.run_id.startsWith("run-"))?.run_id ?? null); })
      .catch((e) => !cancelled && setFeedError(errText(e)));
    return () => { cancelled = true; };
  }, [selected, ticket?.state, latestRunId, activeRun?.run_id]);  // eslint-disable-line react-hooks/exhaustive-deps

  // Load the full history of the run being viewed (unless it's the live one, which polls below).
  useEffect(() => {
    if (!viewRunId || viewRunId === activeRun?.run_id) return;
    let cancelled = false;
    setFeedLoading(true);
    setFeedError(null);
    Promise.all([api.events({ run_id: viewRunId, limit: 500 }), api.run(viewRunId)])
      .then(([ev, run]) => {
        if (cancelled) return;
        setEventsByRun((m) => ({ ...m, [viewRunId]: mergeEvents(m[viewRunId], ev.events) }));
        setRunDetails((m) => ({ ...m, [viewRunId]: run }));
      })
      .catch((e) => !cancelled && setFeedError(errText(e)))
      .finally(() => !cancelled && setFeedLoading(false));
    return () => { cancelled = true; };
  }, [viewRunId, activeRun?.run_id]);

  // Poll the live run: new events, the run's status, and each agent's contribution so far.
  const lastSeen = useRef<Record<string, number>>({});
  useEffect(() => {
    if (!activeRun) return;
    const runId = activeRun.run_id;
    let stop = false;
    const tick = async () => {
      try {
        const [ev, run] = await Promise.all([api.events({ run_id: runId, after: lastSeen.current[runId] ?? -1, limit: 300 }), api.run(runId)]);
        if (stop) return;
        setFeedError(null);
        if (ev.events.length) {
          lastSeen.current[runId] = ev.events[ev.events.length - 1].id;
          setEventsByRun((m) => ({ ...m, [runId]: mergeEvents(m[runId], ev.events) }));
        }
        setRunDetails((m) => ({ ...m, [runId]: run }));
        if (run.status !== "running") {
          stop = true;
          setActiveRun(null);
          await refreshBoard();
          if (run.status === "done") toast("success", `Ticket ${run.ticket_id} is resolved. Check the money desk for anything to approve.`);
          else toast("error", `The run on ticket ${run.ticket_id} stopped: ${run.error ?? "unknown error"}`);
        }
      } catch (e) {
        if (!stop) setFeedError(errText(e));
      }
    };
    tick();
    const h = setInterval(() => !stop && tick(), RUN_POLL_MS);
    return () => { stop = true; clearInterval(h); };
  }, [activeRun?.run_id, refreshBoard, toast]);  // eslint-disable-line react-hooks/exhaustive-deps

  const startRun = async () => {
    if (!ticket || starting || activeRun) return;  // one run at a time; no double clicks
    setStarting(true);
    try {
      const run = await api.runTicket(ticket.id);
      setEventsByRun((m) => ({ ...m, [run.run_id]: [] }));
      setActiveRun(run);
      setViewRunId(run.run_id);
      toast("info", `The agent team is working on ticket ${ticket.id}.`);
      refreshBoard();
    } catch (e) {
      toast("error", errText(e));
      refreshBoard();
    } finally {
      setStarting(false);
    }
  };

  const approve = async (t: Transaction) => {
    if (approving.has(t.id)) return;
    const who = approver.trim();
    if (!who) { toast("error", "Type your name in “Approving as” first."); return; }
    setApproving((s) => new Set(s).add(t.id));
    try {
      const r = await api.approve(t.id, who);
      toast("success", `Approved #${t.id}. ${money(r.amount)} paid; checking ${money(r.balance_before)} → ${money(r.balance_after)}.`);
      if (r.warning) toast("warn", r.warning);
    } catch (e) {
      toast("error", e instanceof ApiError && e.status === 409 ? `Not charged: ${e.message}` : errText(e));
    } finally {
      setApproving((s) => { const n = new Set(s); n.delete(t.id); return n; });
      refreshBoard();
    }
  };

  const reset = async () => {
    if (activeRun || resetting) return;
    if (!resetArmed) { setResetArmed(true); setTimeout(() => setResetArmed(false), 5000); return; }
    setResetting(true);
    try {
      const r = await api.reset();
      setEventsByRun({}); setRunDetails({}); setViewRunId(null); lastSeen.current = {};
      toast("info", `Database reset. Checking is back to ${money(r.checking_balance)}.`);
      await refreshBoard();
    } catch (e) {
      toast("error", errText(e));
    } finally {
      setResetting(false); setResetArmed(false);
    }
  };

  const events = (viewRunId && eventsByRun[viewRunId]) || [];
  const run = viewRunId ? runDetails[viewRunId] ?? null : null;
  const liveHere = !!activeRun && activeRun.ticket_id === selected;
  const pendingCount = txns?.filter((t) => t.status === "pending").length ?? 0;
  const agentsOnRun = useMemo(() => new Set(events.filter((e) => e.action === "run_start").map((e) => e.agent)), [events]);

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="brand__mark" aria-hidden="true">CC</span>
          <div>
            <h1>Campus Customs <span>Agent Desk</span></h1>
            <p>Shop date {shopDate ?? "…"} · five agents, one desk, you hold the checkbook</p>
          </div>
        </div>
        <div className="topbar__right">
          <span className={`conn${offline ? " conn--down" : health?.team_ready ? " conn--up" : ""}`}>
            <span className="conn__dot" aria-hidden="true" />
            {offline ? "Backend offline" : health ? (health.team_ready ? "Backend live · team ready" : "Backend live · team unavailable") : "Connecting…"}
          </span>
          <button className={`btn btn--ghost${resetArmed ? " btn--danger" : ""}`} onClick={reset} disabled={!!activeRun || resetting}
                  title="Restore the database to its original values">
            {resetting ? "Resetting…" : resetArmed ? "Click again to reset" : "Reset database"}
          </button>
        </div>
      </header>

      {offline && <div className="banner banner--error" role="alert">{offline}</div>}
      {health && !health.team_ready && <div className="banner banner--warn">The agent team isn't available: {health.team_error}</div>}

      <main className="layout">
        <TicketList tickets={tickets} error={ticketsError} selected={selected} runningTicket={activeRun?.ticket_id ?? null} onSelect={setSelected} />

        <div className="stage">
          {ticket ? (
            <section className={`panel ticket-stage${ticket.state === "resolved" ? " ticket-stage--resolved" : ""}`} aria-label={`Ticket ${ticket.id}`}>
              {ticket.state === "resolved" && !liveHere && <span className="stamp" aria-hidden="true">Resolved</span>}
              <div className="ticket-stage__head">
                <div>
                  <p className="eyebrow">Ticket #{ticket.id} · {ticket.requester}</p>
                  <h2>{ticket.subject}</h2>
                  <p className="ticket-stage__note">“{ticket.notes?.split("\n")[0]}”</p>
                </div>
                {ticketPill(ticket, activeRun?.ticket_id ?? null)}
              </div>
              <div className="ticket-stage__actions">
                <button className="btn btn--primary btn--big" onClick={startRun}
                        disabled={!!activeRun || starting || ticket.state === "resolved" || !health?.team_ready}>
                  {starting ? <><span className="spinner spinner--light" /> Starting…</>
                    : liveHere ? <><span className="spinner spinner--light" /> Agents working…</>
                    : ticket.state === "resolved" ? "✓ Resolved by the team"
                    : activeRun ? `Busy with ticket ${activeRun.ticket_id}` : "Start the agent team"}
                </button>
                <div className="crew">
                  {(["boss", ...SPECIALISTS] as const).map((a) => (
                    <span key={a} className={`crew__member${agentsOnRun.has(a) ? " crew__member--on" : ""}`} title={`${AGENTS[a].name}: ${AGENTS[a].role}`}>
                      <Avatar who={a} size={26} />
                    </span>
                  ))}
                  <span className="muted">{agentsOnRun.size ? `${agentsOnRun.size} of 5 agents worked this ticket` : "The team is standing by"}</span>
                </div>
              </div>
              <TeamMap events={events} running={liveHere} />
              {pendingCount > 0 && ticket.state === "resolved" && (
                <p className="nudge">→ {pendingCount} transaction{pendingCount > 1 ? "s are" : " is"} waiting on the money desk. The agents prepared them, and only you can approve.</p>
              )}
            </section>
          ) : (
            <section className="panel"><div className="skeleton skeleton--card" /></section>
          )}
          <ActivityFeed events={events} loading={feedLoading || (liveHere && events.length === 0)} error={feedError} running={liveHere} />
          <Contributions run={run} loading={feedLoading} />
        </div>

        <MoneyDesk cash={cash} cashError={cashError} txns={txns} txnError={txnError}
                   approver={approver} setApprover={setApprover} approving={approving} onApprove={approve} />
      </main>

      <div className="toasts" aria-live="polite">
        {toasts.map((t) => <div key={t.id} className={`toast toast--${t.kind}`}>{t.text}</div>)}
      </div>
    </div>
  );
}
