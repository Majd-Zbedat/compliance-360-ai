/** Status pills from Figma DocumentsScreen — dot + label on tinted background. */

export type DocStatus =
  | "compliant"
  | "non-compliant"
  | "review"
  | "partial"
  | "analyzed"
  | "pending"
  | "processing"
  | "failed"
  | "Done"
  | "Rejected"
  | "Drafting"
  | "Approved"
  | "Pending"
  | "unreviewed";

const config: Record<
  string,
  { label: string; bg: string; text: string; dot: string }
> = {
  compliant: { label: "Compliant", bg: "#F0F9E8", text: "#2D6A0A", dot: "#86BC25" },
  "non-compliant": { label: "Non-Compliant", bg: "#FEF2F2", text: "#991B1B", dot: "#EF4444" },
  review: { label: "Under Review", bg: "#FFF7ED", text: "#92400E", dot: "#F59E0B" },
  partial: { label: "Partial", bg: "#FFF7ED", text: "#92400E", dot: "#F59E0B" },
  analyzed: { label: "Analyzed", bg: "#F0F9E8", text: "#2D6A0A", dot: "#86BC25" },
  Done: { label: "Analyzed", bg: "#F0F9E8", text: "#2D6A0A", dot: "#86BC25" },
  pending: { label: "Pending", bg: "#F1F5F9", text: "#475569", dot: "#94A3B8" },
  Drafting: { label: "Processing", bg: "#EFF6FF", text: "#1D4ED8", dot: "#3B82F6" },
  processing: { label: "Processing", bg: "#EFF6FF", text: "#1D4ED8", dot: "#3B82F6" },
  failed: { label: "Failed", bg: "#FEF2F2", text: "#991B1B", dot: "#EF4444" },
  Rejected: { label: "Rejected", bg: "#FEF2F2", text: "#991B1B", dot: "#EF4444" },
  // Human review decisions
  Approved: { label: "Approved", bg: "#F0F9E8", text: "#166534", dot: "#16A34A" },
  Pending:  { label: "Pending Review", bg: "#FFFBEB", text: "#92400E", dot: "#F59E0B" },
  unreviewed: { label: "Unreviewed", bg: "#F1F5F9", text: "#64748B", dot: "#CBD5E1" },
};

export function StatusBadge({ status }: { status: string }) {
  const c = config[status] ?? config.pending;
  return (
    <span
      className="inline-flex items-center gap-1.5 whitespace-nowrap rounded px-2.5 py-1 text-xs font-medium"
      style={{ backgroundColor: c.bg, color: c.text }}
    >
      <span className="h-1.5 w-1.5 shrink-0 rounded-full" style={{ backgroundColor: c.dot }} />
      {c.label}
    </span>
  );
}
