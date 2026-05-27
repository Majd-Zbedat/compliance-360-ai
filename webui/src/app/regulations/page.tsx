"use client";

import { useEffect, useMemo, useState } from "react";
import { ChevronDown, Plus, RefreshCw, Search } from "lucide-react";
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
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api, type Regulation } from "@/lib/api";

const categoryMap: Record<string, string> = {
  GDPR: "Data Privacy",
  ISO27001: "Operational",
  LocalLaw: "Financial",
};

const jurisdictionMap: Record<string, string> = {
  GDPR: "EU / GDPR",
  ISO27001: "Global",
  LocalLaw: "US Federal",
};

const statuses = ["compliant", "review", "partial", "non-compliant"] as const;

function mockStatus(id: string) {
  let h = 0;
  for (let i = 0; i < id.length; i++) h = (h << 5) - h + id.charCodeAt(i);
  return statuses[Math.abs(h) % statuses.length];
}

function mockDate(seed: string, offsetDays: number) {
  let h = 0;
  for (let i = 0; i < seed.length; i++) h = (h << 5) - h + seed.charCodeAt(i);
  const d = new Date(2024, 11, 1);
  d.setDate(d.getDate() - (Math.abs(h) % 90) + offsetDays);
  return d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}

function CategoryPill({ label }: { label: string }) {
  return (
    <span className="inline-flex rounded px-2.5 py-1 text-xs font-medium" style={{ backgroundColor: "#EFF6FF", color: "#1D4ED8" }}>
      {label}
    </span>
  );
}

export default function RegulationsPage() {
  const [items, setItems] = useState<Regulation[]>([]);
  const [query, setQuery] = useState("");
  const [jurisdiction, setJurisdiction] = useState("All");
  const [category, setCategory] = useState("All");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api
      .regulations()
      .then((rows) => {
        if (!cancelled) setItems(rows);
      })
      .catch((err) => {
        if (!cancelled) setError(err?.message || "Failed to load regulations");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return items.filter((r) => {
      const cat = categoryMap[r.source] || "General";
      const jur = jurisdictionMap[r.source] || r.source;
      const matchQ =
        !q ||
        r.article.toLowerCase().includes(q) ||
        (r.title || "").toLowerCase().includes(q) ||
        r.text.toLowerCase().includes(q);
      const matchJ = jurisdiction === "All" || jur === jurisdiction;
      const matchC = category === "All" || cat === category;
      return matchQ && matchJ && matchC;
    });
  }, [items, query, jurisdiction, category]);

  const jurisdictions = ["All", ...new Set(items.map((r) => jurisdictionMap[r.source] || r.source))];
  const categories = ["All", ...new Set(items.map((r) => categoryMap[r.source] || "General"))];

  return (
    <div className="mx-auto max-w-[1200px] space-y-6 p-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-primary">Global Regulation Library</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {items.length} regulations tracked across all jurisdictions
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" className="gap-2">
            <RefreshCw size={14} />
            Sync Library
          </Button>
          <Button size="sm" className="gap-2 bg-primary hover:bg-primary/90">
            <Plus size={14} />
            Add Regulation
          </Button>
        </div>
      </div>

      <AuditTable>
        <AuditTableToolbar>
          <div className="relative min-w-0 flex-1">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              className="h-10 pl-9"
              placeholder="Search regulations..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>
          <FilterSelect value={jurisdiction} options={jurisdictions} onChange={setJurisdiction} />
          <FilterSelect value={category} options={categories} onChange={setCategory} />
        </AuditTableToolbar>

        <AuditTableScroll>
          <AuditTableElement>
            <AuditTableHeader>
              <AuditTableHeaderRow>
                <AuditTableHead>Regulation</AuditTableHead>
                <AuditTableHead>Jurisdiction</AuditTableHead>
                <AuditTableHead>Category</AuditTableHead>
                <AuditTableHead>Compliance Status</AuditTableHead>
                <AuditTableHead>Last Review</AuditTableHead>
                <AuditTableHead>Next Review</AuditTableHead>
              </AuditTableHeaderRow>
            </AuditTableHeader>
            <AuditTableBody>
              {loading ? (
                <AuditTableRow className="cursor-default hover:bg-transparent">
                  <AuditTableCell colSpan={6} className="py-12 text-center text-sm text-muted-foreground">
                    Loading regulations…
                  </AuditTableCell>
                </AuditTableRow>
              ) : error ? (
                <AuditTableRow className="cursor-default hover:bg-transparent">
                  <AuditTableCell colSpan={6} className="py-12 text-center text-sm text-destructive">
                    {error}
                  </AuditTableCell>
                </AuditTableRow>
              ) : filtered.length === 0 ? (
                <AuditTableRow className="cursor-default hover:bg-transparent">
                  <AuditTableCell colSpan={6} className="py-12 text-center text-sm text-muted-foreground">
                    No regulations match your filters.
                  </AuditTableCell>
                </AuditTableRow>
              ) : (
                filtered.map((r) => (
                  <AuditTableRow key={r.id} className="cursor-default">
                    <AuditTableCell>
                      <p className="text-sm font-semibold text-brand-ink">{r.article}</p>
                      {r.title && <p className="text-xs text-muted-foreground">{r.title}</p>}
                    </AuditTableCell>
                    <AuditTableCell className="text-sm text-brand-ink">
                      {jurisdictionMap[r.source] || r.source}
                    </AuditTableCell>
                    <AuditTableCell>
                      <CategoryPill label={categoryMap[r.source] || "General"} />
                    </AuditTableCell>
                    <AuditTableCell>
                      <StatusBadge status={mockStatus(r.id)} />
                    </AuditTableCell>
                    <AuditTableCell className="text-sm text-muted-foreground">
                      {mockDate(r.id, 0)}
                    </AuditTableCell>
                    <AuditTableCell className="text-sm text-muted-foreground">
                      {mockDate(r.id, -120)}
                    </AuditTableCell>
                  </AuditTableRow>
                ))
              )}
            </AuditTableBody>
          </AuditTableElement>
        </AuditTableScroll>

        <AuditTableFooter>
          <p className="text-xs text-muted-foreground">
            Showing {filtered.length} of {items.length} regulation{items.length !== 1 ? "s" : ""}
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
    </div>
  );
}

function FilterSelect({
  value,
  options,
  onChange,
}: {
  value: string;
  options: string[];
  onChange: (v: string) => void;
}) {
  return (
    <div className="relative">
      <select
        className="h-10 appearance-none rounded-md border border-border bg-card py-2 pl-3 pr-8 text-sm text-brand-ink"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      >
        {options.map((o) => (
          <option key={o} value={o}>
            {o}
          </option>
        ))}
      </select>
      <ChevronDown className="pointer-events-none absolute right-2 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
    </div>
  );
}
