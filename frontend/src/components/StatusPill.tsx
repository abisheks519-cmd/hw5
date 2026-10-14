// Ticket and run states. Each pairs a status color with an icon and a word, never color alone.
export type PillKind = "open" | "running" | "resolved" | "failed" | "pending" | "approved";

const LABEL: Record<PillKind, string> = {
  open: "Open", running: "Agents working", resolved: "Resolved", failed: "Run failed", pending: "Needs approval", approved: "Approved",
};
const ICON: Record<PillKind, string> = { open: "●", running: "", resolved: "✓", failed: "✕", pending: "!", approved: "✓" };

export function StatusPill({ kind, label }: { kind: PillKind; label?: string }) {
  return (
    <span className={`pill pill--${kind}`}>
      <span className="pill__icon" aria-hidden="true">{kind === "running" ? <span className="spinner" /> : ICON[kind]}</span>
      {label ?? LABEL[kind]}
    </span>
  );
}
