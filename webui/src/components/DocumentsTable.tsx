"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { ChevronDown, FileText, MoreVertical, Search, Upload } from "lucide-react";
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
import type { AuditSummary } from "@/lib/api";
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

export function DocumentsTable({ audits }: { audits: AuditSummary[] }) {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("All");

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
      return matchQ && matchF;
    });
  }, [audits, query, filter]);

  return (
    <AuditTable>
      <AuditTableToolbar>
        <div className="relative min-w-0 flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            className="h-10 pl-9"
            placeholder="Search documents or analysts..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
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
              <AuditTableHead>AI Analysis Status</AuditTableHead>
              <AuditTableHead>Assigned Analyst</AuditTableHead>
              <AuditTableHead>Date</AuditTableHead>
              <AuditTableHead className="w-10" />
            </AuditTableHeaderRow>
          </AuditTableHeader>
          <AuditTableBody>
            {filtered.length === 0 ? (
              <AuditTableRow className="cursor-default hover:bg-transparent">
                <AuditTableCell colSpan={6} className="py-12 text-center text-sm text-muted-foreground">
                  No documents match your search.
                </AuditTableCell>
              </AuditTableRow>
            ) : (
              filtered.map((a) => (
                <AuditTableRow key={a.id} onClick={() => router.push(`/audits/${a.id}`)}>
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
                  <AuditTableCell className="text-sm text-brand-ink">US Federal</AuditTableCell>
                  <AuditTableCell>
                    <StatusBadge status={mapStatus(a.status)} />
                  </AuditTableCell>
                  <AuditTableCell>
                    <AnalystAvatar name={a.requester || "Sarah Chen"} />
                  </AuditTableCell>
                  <AuditTableCell className="text-sm text-muted-foreground">
                    {formatDateTime(a.created_at).split(",")[0]}
                  </AuditTableCell>
                  <AuditTableCell>
                    <button
                      type="button"
                      className="rounded p-1 text-muted-foreground hover:bg-muted"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <MoreVertical size={16} />
                    </button>
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
