"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, useMemo } from "react";
import {
  Check,
  ChevronDown,
  Clock,
  FileText,
  MoreVertical,
  Search,
  Trash2,
  Upload,
  X,
} from "lucide-react";
import {
  AuditTable,
  AuditTableBody,
  AuditTableCell,
  AuditTableElement,
  AuditTableFooter,
  AuditTableHead,
  AuditTableHeader,
  AuditTableHeaderRow,
  AuditTableRow,
  AuditTableScroll,
  AuditTableToolbar,
} from "@/components/AuditTable";
import { AnalystAvatar } from "@/components/AnalystAvatar";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api, type AuditSummary } from "@/lib/api";
import { formatDateTime } from "@/lib/utils";

function mockFileSize(name: string) {
  const kb = (name.length * 47) % 2400 + 400;
  return kb >= 1024 ? `${(kb / 1024).toFixed(1)} MB` : `${kb} KB`;
}

function mapStatus(status: string) {
  if (status === "Done") return "analyzed";
  if (status === "Drafting" || status === "Reviewing" || status === "Flagging") return "processing";
  if (status === "Rejected") return "failed";
  return "pending";
}

// ─── Action menu (⋮) ─────────────────────────────────────────────────────────

type ReviewStatus = "Approved" | "Pending" | "Rejected";

interface ActionMenuProps {
  auditId: string;
  current: ReviewStatus | null;
  onStatusChange: (id: string, status: ReviewStatus) => void;
  onDelete: (id: string) => void;
}

function ActionMenu({ auditId, current, onStatusChange, onDelete }: ActionMenuProps) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handler(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    if (open) document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  const actions: { label: string; value: ReviewStatus; icon: React.ReactNode; color: string }[] = [
    { label: "Approve", value: "Approved", icon: <Check size={13} />, color: "text-green-700" },
    { label: "Mark Pending", value: "Pending", icon: <Clock size={13} />, color: "text-amber-700" },
    { label: "Reject", value: "Rejected", icon: <X size={13} />, color: "text-red-700" },
  ];

  async function handleClick(value: ReviewStatus) {
    setOpen(false);
    if (value === current) return;
    setLoading(true);
    try {
      await api.updateReviewStatus(auditId, value);
      onStatusChange(auditId, value);
    } catch (err) {
      console.error("Status update failed", err);
    } finally {
      setLoading(false);
    }
  }

  async function handleDelete() {
    setOpen(false);
    if (!window.confirm("Delete this document permanently? This cannot be undone.")) {
      return;
    }
    setLoading(true);
    try {
      await api.deleteAudit(auditId);
      onDelete(auditId);
    } catch (err) {
      console.error("Delete failed", err);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        disabled={loading}
        className="rounded p-1 text-muted-foreground hover:bg-muted disabled:opacity-40"
        onClick={(e) => {
          e.stopPropagation();
          setOpen((o) => !o);
        }}
      >
        <MoreVertical size={16} />
      </button>

      {open && (
        <div
          className="absolute right-0 top-full z-50 mt-1 min-w-[155px] rounded-lg border border-border bg-card py-1 shadow-lg"
          onClick={(e) => e.stopPropagation()}
        >
          <p className="px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
            Set Review Status
          </p>
          {actions.map((a) => (
            <button
              key={a.value}
              type="button"
              onClick={() => handleClick(a.value)}
              className={`flex w-full items-center gap-2 px-3 py-2 text-sm hover:bg-muted ${a.color} ${
                current === a.value ? "font-semibold" : ""
              }`}
            >
              {a.icon}
              {a.label}
              {current === a.value && (
                <span className="ml-auto text-[10px] opacity-60">current</span>
              )}
            </button>
          ))}
          <div className="my-1 border-t border-border" />
          <button
            type="button"
            onClick={handleDelete}
            className="flex w-full items-center gap-2 px-3 py-2 text-sm text-red-700 hover:bg-red-50"
          >
            <Trash2 size={13} />
            Delete document
          </button>
        </div>
      )}
    </div>
  );
}

// ─── Main table ───────────────────────────────────────────────────────────────

export function DocumentsTable({ audits: initial }: { audits: AuditSummary[] }) {
  const router = useRouter();
  const [audits, setAudits] = useState<AuditSummary[]>(initial);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("All");
  const [reviewFilter, setReviewFilter] = useState("All");

  // Optimistic review_status update
  function handleStatusChange(id: string, status: ReviewStatus) {
    setAudits((prev) =>
      prev.map((a) => (a.id === id ? { ...a, review_status: status } : a))
    );
  }

  // Remove a deleted document from the list
  function handleDelete(id: string) {
    setAudits((prev) => prev.filter((a) => a.id !== id));
  }

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return audits.filter((a) => {
      const matchQ =
        !q ||
        a.filename.toLowerCase().includes(q) ||
        (a.requester || "").toLowerCase().includes(q);
      const matchF =
        filter === "All" ||
        (filter === "Analyzed" && a.status === "Done") ||
        (filter === "Processing" && ["Drafting", "Reviewing", "Flagging"].includes(a.status)) ||
        (filter === "Failed" && a.status === "Rejected");
      const matchR =
        reviewFilter === "All" ||
        (reviewFilter === "Approved" && a.review_status === "Approved") ||
        (reviewFilter === "Pending" && a.review_status === "Pending") ||
        (reviewFilter === "Rejected" && a.review_status === "Rejected") ||
        (reviewFilter === "Unreviewed" && !a.review_status);
      return matchQ && matchF && matchR;
    });
  }, [audits, query, filter, reviewFilter]);

  return (
    <AuditTable>
      <AuditTableToolbar>
        {/* Search */}
        <div className="relative min-w-0 flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            className="h-10 pl-9"
            placeholder="Search documents or analysts..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>

        {/* AI status filter */}
        <div className="relative">
          <select
            className="h-10 appearance-none rounded-md border border-border bg-card py-2 pl-3 pr-8 text-sm text-brand-ink"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          >
            {["All", "Analyzed", "Processing", "Failed"].map((o) => (
              <option key={o}>{o}</option>
            ))}
          </select>
          <ChevronDown className="pointer-events-none absolute right-2 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        </div>

        {/* Review status filter */}
        <div className="relative">
          <select
            className="h-10 appearance-none rounded-md border border-border bg-card py-2 pl-3 pr-8 text-sm text-brand-ink"
            value={reviewFilter}
            onChange={(e) => setReviewFilter(e.target.value)}
          >
            {["All", "Approved", "Pending", "Rejected", "Unreviewed"].map((o) => (
              <option key={o}>{o}</option>
            ))}
          </select>
          <ChevronDown className="pointer-events-none absolute right-2 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        </div>

        <Button asChild className="shrink-0 gap-2 bg-primary hover:bg-primary/90">
          <Link href="/audits/new">
            <Upload size={14} />
            Upload Document
          </Link>
        </Button>
      </AuditTableToolbar>

      <AuditTableScroll>
        <AuditTableElement>
          <AuditTableHeader>
            <AuditTableHeaderRow>
              <AuditTableHead>Document Name</AuditTableHead>
              <AuditTableHead>Jurisdiction</AuditTableHead>
              <AuditTableHead>AI Analysis</AuditTableHead>
              <AuditTableHead>Review Decision</AuditTableHead>
              <AuditTableHead>Assigned Analyst</AuditTableHead>
              <AuditTableHead>Date</AuditTableHead>
              <AuditTableHead className="w-10" />
            </AuditTableHeaderRow>
          </AuditTableHeader>
          <AuditTableBody>
            {filtered.length === 0 ? (
              <AuditTableRow className="cursor-default hover:bg-transparent">
                <AuditTableCell colSpan={7} className="py-12 text-center text-sm text-muted-foreground">
                  No documents match your search.
                </AuditTableCell>
              </AuditTableRow>
            ) : (
              filtered.map((a) => (
                <AuditTableRow key={a.id} onClick={() => router.push(`/audits/${a.id}`)}>
                  {/* Document name */}
                  <AuditTableCell>
                    <div className="flex items-center gap-3">
                      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-secondary">
                        <FileText size={16} className="text-primary" />
                      </div>
                      <div className="min-w-0">
                        <p className="truncate text-sm font-semibold text-brand-ink">{a.filename}</p>
                        <p className="text-xs text-muted-foreground">{mockFileSize(a.filename)}</p>
                      </div>
                    </div>
                  </AuditTableCell>

                  {/* Jurisdiction */}
                  <AuditTableCell className="text-sm text-brand-ink">US Federal</AuditTableCell>

                  {/* AI Analysis status */}
                  <AuditTableCell>
                    <StatusBadge status={mapStatus(a.status)} />
                  </AuditTableCell>

                  {/* Human review decision */}
                  <AuditTableCell>
                    <StatusBadge status={a.review_status ?? "Pending"} />
                  </AuditTableCell>

                  {/* Analyst */}
                  <AuditTableCell>
                    <AnalystAvatar name={a.requester || "Majd Zubeidat"} />
                  </AuditTableCell>

                  {/* Date */}
                  <AuditTableCell className="text-sm text-muted-foreground">
                    {formatDateTime(a.created_at).split(",")[0]}
                  </AuditTableCell>

                  {/* Actions ⋮ */}
                  <AuditTableCell>
                    <ActionMenu
                      auditId={a.id}
                      current={(a.review_status as ReviewStatus) ?? null}
                      onStatusChange={handleStatusChange}
                      onDelete={handleDelete}
                    />
                  </AuditTableCell>
                </AuditTableRow>
              ))
            )}
          </AuditTableBody>
        </AuditTableElement>
      </AuditTableScroll>

      <AuditTableFooter>
        <p className="text-xs text-muted-foreground">
          Showing {filtered.length} of {audits.length} document{audits.length !== 1 ? "s" : ""}
        </p>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" disabled>
            Previous
          </Button>
          <Button size="sm" className="bg-primary hover:bg-primary/90" disabled>
            Next
          </Button>
        </div>
      </AuditTableFooter>
    </AuditTable>
  );
}
