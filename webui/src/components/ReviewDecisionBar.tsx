"use client";

import { useState } from "react";
import { Check, Clock, X, Loader2 } from "lucide-react";
import { api } from "@/lib/api";

type ReviewStatus = "Approved" | "Pending" | "Rejected";

const OPTIONS: {
  value: ReviewStatus;
  label: string;
  icon: React.ReactNode;
  active: string;
  idle: string;
}[] = [
  {
    value: "Approved",
    label: "Approve",
    icon: <Check size={14} />,
    active: "bg-green-600 text-white border-green-600 shadow-sm",
    idle: "border-border text-muted-foreground hover:border-green-500 hover:text-green-700 hover:bg-green-50",
  },
  {
    value: "Pending",
    label: "Pending",
    icon: <Clock size={14} />,
    active: "bg-amber-500 text-white border-amber-500 shadow-sm",
    idle: "border-border text-muted-foreground hover:border-amber-400 hover:text-amber-700 hover:bg-amber-50",
  },
  {
    value: "Rejected",
    label: "Reject",
    icon: <X size={14} />,
    active: "bg-red-600 text-white border-red-600 shadow-sm",
    idle: "border-border text-muted-foreground hover:border-red-500 hover:text-red-700 hover:bg-red-50",
  },
];

export function ReviewDecisionBar({
  auditId,
  initialStatus,
}: {
  auditId: string;
  initialStatus?: string | null;
}) {
  const [current, setCurrent] = useState<ReviewStatus>(
    (initialStatus as ReviewStatus) ?? "Pending"
  );
  const [loading, setLoading] = useState<ReviewStatus | null>(null);
  const [saved, setSaved] = useState(false);

  async function handleClick(value: ReviewStatus) {
    if (value === current || loading) return;
    setLoading(value);
    setSaved(false);
    try {
      await api.updateReviewStatus(auditId, value);
      setCurrent(value);
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch (err) {
      console.error("Review status update failed", err);
    } finally {
      setLoading(null);
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-3 rounded-lg border border-border bg-card px-4 py-3">
      <span className="text-sm font-medium text-brand-ink">Review Decision:</span>

      <div className="flex gap-2">
        {OPTIONS.map((opt) => {
          const isActive = current === opt.value;
          const isLoading = loading === opt.value;
          return (
            <button
              key={opt.value}
              type="button"
              disabled={!!loading}
              onClick={() => handleClick(opt.value)}
              className={`inline-flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-sm font-medium transition-all disabled:cursor-not-allowed disabled:opacity-60 ${
                isActive ? opt.active : opt.idle
              }`}
            >
              {isLoading ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                opt.icon
              )}
              {opt.label}
            </button>
          );
        })}
      </div>

      {saved && (
        <span className="flex items-center gap-1 text-xs text-green-600">
          <Check size={12} /> Saved
        </span>
      )}
    </div>
  );
}
