// Typed client for the FastAPI backend in backend/main.py. Every number on the dashboard comes from here.

export const API_BASE: string = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

export type AgentName = "boss" | "inventory" | "accounting" | "facilities" | "customer_service";
export type Actor = AgentName | "team" | "human";

export interface RunInfo {
  run_id: string;
  ticket_id: number;
  status: "running" | "done" | "failed";
  started_at: string;
  finished_at: string | null;
  outcome: TicketOutcome | null;
  error: string | null;
}

export interface Ticket {
  id: number;
  type: string;
  requester: string;
  subject: string;
  sku: string | null;
  size: string | null;
  qty: number | null;
  lease_id: number | null;
  invoice_id: number | null;
  status: string;
  notes: string | null;
  created_at: string;
  state: "open" | "resolved";
  latest_run: RunInfo | null;
}

export interface Fact { label: string; value: string; source_tool: string }
export interface Approval { action: string; amount: number | null; reason: string }

export interface TicketOutcome {
  ticket_id: number;
  status: string;
  summary: string;
  delegated_to: AgentName[];
  facts: Fact[];
  approvals_needed: Approval[];
  reply_draft: string | null;
  next_steps: string[];
}

export interface Contribution {
  agent: AgentName;
  times_asked: number;
  asked_by: AgentName[];
  summary: string | null;
  tools_used: { tool: string; calls: number }[];
  handed_off_to: AgentName[];
  actions_taken: string[];
  approvals_needed: Approval[];
  reply_draft: string | null;
  errors: string[];
}

export interface RunDetail extends RunInfo { contributions: Contribution[] }

export interface AgentEvent {
  id: number;
  ts: string;
  run_id: string;
  ticket_id: number | null;
  agent: Actor;
  chain: string[];
  step: number;
  action: string;
  tool: string | null;
  message: string;
  inputs: unknown;
  result: unknown;
  error: string | null;
}

export interface Transaction {
  id: number;
  kind: "invoice" | "rent" | "purchase";
  ref_id: number | null;
  ref_due: string | null;
  sku: string | null;
  size: string | null;
  qty: number | null;
  vendor_id: number | null;
  amount: number;
  description: string;
  ticket_id: number | null;
  prepared_by: AgentName;
  prepared_at: string;
  status: "pending" | "approved";
  approved_by: string | null;
  approved_at: string | null;
  payment_id: number | null;
}

export interface ApprovalReceipt {
  transaction: Transaction;
  payment_id: number;
  amount: number;
  balance_before: number;
  balance_after: number;
  effect: string;
  warning: string | null;
}

export interface Cash { account: string; balance: number; as_of: string; shop_date: string | null }
export interface Health { ok: boolean; team_ready: boolean; team_error: string | null; database: string; running: string[] }

export class ApiError extends Error {
  constructor(public status: number, message: string, public code?: string) {
    super(message);
  }
}

function detailMessage(body: unknown, status: number): { message: string; code?: string } {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return { message: detail };
  if (Array.isArray(detail)) return { message: detail.map((d) => d?.msg ?? String(d)).join("; ") };
  if (detail && typeof detail === "object" && "message" in detail) {
    const d = detail as { message: string; code?: string };
    return { message: d.message, code: d.code };
  }
  return { message: `Request failed (HTTP ${status})` };
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(API_BASE + path, init);
  } catch {
    throw new ApiError(0, `Can't reach the backend at ${API_BASE}. Start it from backend/ with: uvicorn main:app --reload --port 8000`);
  }
  const text = await res.text();
  let body: unknown = null;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    body = null;
  }
  if (!res.ok) {
    const { message, code } = detailMessage(body, res.status);
    throw new ApiError(res.status, message, code);
  }
  return body as T;
}

const post = <T>(path: string, json?: unknown) =>
  request<T>(path, {
    method: "POST",
    headers: json === undefined ? undefined : { "Content-Type": "application/json" },
    body: json === undefined ? undefined : JSON.stringify(json),
  });

export const api = {
  health: () => request<Health>("/api/health"),
  tickets: () => request<{ shop_date: string | null; tickets: Ticket[] }>("/api/tickets"),
  runTicket: (ticketId: number) => post<RunInfo>(`/api/tickets/${ticketId}/run`),
  run: (runId: string) => request<RunDetail>(`/api/runs/${runId}`),
  events: (q: { run_id?: string; ticket_id?: number; after?: number; limit?: number }) => {
    const params = new URLSearchParams();
    Object.entries(q).forEach(([k, v]) => v !== undefined && params.set(k, String(v)));
    return request<{ events: AgentEvent[]; last_id: number }>(`/api/events?${params}`);
  },
  transactions: (status: "pending" | "approved" | "all" = "all") =>
    request<{ transactions: Transaction[]; pending_total: number }>(`/api/transactions?status=${status}`),
  approve: (txnId: number, approvedBy: string) =>
    post<ApprovalReceipt>(`/api/transactions/${txnId}/approve`, { approved_by: approvedBy }),
  cash: () => request<Cash>("/api/cash"),
  reset: () => post<{ reset: boolean; checking_balance: number }>("/api/reset"),
};

export const money = (n: number) =>
  n.toLocaleString("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 2 });
