"use client";

import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, ChevronDown, Loader2, Plus, RefreshCw, Search, X } from "lucide-react";
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
  ISO42001: "AI Governance",
  LocalLaw: "Financial",
  SOX: "Financial",
  PCI_DSS: "Financial",
  AML_KYC: "Financial",
  BaselIII: "Financial",
  NIST_CSF: "Cybersecurity",
  SOC2: "Cybersecurity",
  HIPAA: "Healthcare",
  PrivacyControls: "Data Privacy",
};

const jurisdictionMap: Record<string, string> = {
  GDPR: "EU / GDPR",
  ISO27001: "Global",
  ISO42001: "Global",
  LocalLaw: "US Federal",
  SOX: "US Federal",
  PCI_DSS: "Global",
  AML_KYC: "Global",
  BaselIII: "Global",
  NIST_CSF: "US Federal",
  SOC2: "US / AICPA",
  HIPAA: "US Federal",
  PrivacyControls: "Global",
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
  const [reloadKey, setReloadKey] = useState(0);
  const [modalOpen, setModalOpen] = useState(false);

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
  }, [reloadKey]);

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
          <Button
            variant="outline"
            size="sm"
            className="gap-2"
            onClick={() => setReloadKey((k) => k + 1)}
          >
            <RefreshCw size={14} />
            Sync Library
          </Button>
          <Button
            size="sm"
            className="gap-2 bg-primary hover:bg-primary/90"
            onClick={() => setModalOpen(true)}
          >
            <Plus size={14} />
            Add Regulation
          </Button>
        </div>
      </div>

      {modalOpen && (
        <AddRegulationModal
          onClose={() => setModalOpen(false)}
          onAdded={() => {
            setModalOpen(false);
            setReloadKey((k) => k + 1);
          }}
        />
      )}

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

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result;
      if (typeof result === "string") {
        const idx = result.indexOf(",");
        resolve(idx >= 0 ? result.slice(idx + 1) : result);
      } else {
        reject(new Error("Failed to read file"));
      }
    };
    reader.onerror = () => reject(reader.error || new Error("Failed to read file"));
    reader.readAsDataURL(file);
  });
}

function AddRegulationModal({
  onClose,
  onAdded,
}: {
  onClose: () => void;
  onAdded: () => void;
}) {
  const [mode, setMode] = useState<"text" | "file">("text");
  const [source, setSource] = useState("");
  const [article, setArticle] = useState("");
  const [title, setTitle] = useState("");
  const [text, setText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const submit = async () => {
    setError(null);
    setNotice(null);
    if (!source.trim()) {
      setError("Source name is required (e.g. GDPR, SOX, Custom).");
      return;
    }
    if (mode === "text" && !text.trim()) {
      setError("Paste the regulation text, or switch to file upload.");
      return;
    }
    if (mode === "file" && !file) {
      setError("Choose a PDF or text file, or switch to pasting text.");
      return;
    }
    setBusy(true);
    try {
      const payload: Parameters<typeof api.addRegulation>[0] = {
        source: source.trim(),
        article: article.trim() || undefined,
        title: title.trim() || undefined,
        tags: [],
      };
      if (mode === "text") {
        payload.text = text;
      } else if (file) {
        payload.document_b64 = await fileToBase64(file);
        payload.filename = file.name;
      }
      const res = await api.addRegulation(payload);
      if (res.warning) {
        setNotice(res.warning);
      }
      onAdded();
    } catch (err: any) {
      setError(err?.message || "Failed to add regulation");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-lg rounded-lg border border-border bg-card p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-start justify-between">
          <div>
            <h2 className="text-lg font-semibold text-primary">Add Regulation</h2>
            <p className="text-sm text-muted-foreground">
              Index a new source into the audit knowledge base (paste text or upload a PDF).
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-muted-foreground hover:text-foreground"
            aria-label="Close"
          >
            <X size={18} />
          </button>
        </div>

        <div className="mb-4 inline-flex rounded-md border border-border p-0.5 text-sm">
          {(["text", "file"] as const).map((m) => (
            <button
              key={m}
              onClick={() => setMode(m)}
              className={
                "rounded px-3 py-1.5 font-medium transition-colors " +
                (mode === m
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:bg-muted")
              }
            >
              {m === "text" ? "Paste text" : "Upload PDF / TXT"}
            </button>
          ))}
        </div>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <ModalField label="Source *" placeholder="GDPR, SOX, Custom…" value={source} onChange={setSource} />
          <ModalField label="Article / section" placeholder="Art. 32, Sec. 404…" value={article} onChange={setArticle} />
        </div>
        <div className="mt-3">
          <ModalField label="Title (optional)" placeholder="Security of processing" value={title} onChange={setTitle} />
        </div>

        {mode === "text" ? (
          <div className="mt-3 flex flex-col gap-1">
            <span className="text-xs font-medium text-muted-foreground">Regulation text *</span>
            <textarea
              rows={6}
              className="rounded-md border border-border bg-white px-3 py-2 text-sm text-brand-ink outline-none focus:border-accent"
              placeholder="Paste the clauses / control text here. Separate distinct clauses with a blank line."
              value={text}
              onChange={(e) => setText(e.target.value)}
            />
          </div>
        ) : (
          <div className="mt-3 flex flex-col gap-1">
            <span className="text-xs font-medium text-muted-foreground">Document (PDF or .txt) *</span>
            <input
              type="file"
              accept=".pdf,.txt"
              className="text-sm"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
            />
          </div>
        )}

        {notice && (
          <div className="mt-4 flex items-start gap-2 rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-800">
            <AlertTriangle size={16} className="mt-0.5 shrink-0" />
            <span>{notice}</span>
          </div>
        )}
        {error && (
          <div className="mt-4 flex items-start gap-2 rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
            <AlertTriangle size={16} className="mt-0.5 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <div className="mt-6 flex justify-end gap-2">
          <Button variant="outline" size="sm" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button size="sm" className="gap-2 bg-primary hover:bg-primary/90" onClick={submit} disabled={busy}>
            {busy && <Loader2 size={14} className="animate-spin" />}
            {busy ? "Indexing…" : "Add to library"}
          </Button>
        </div>
      </div>
    </div>
  );
}

function ModalField({
  label,
  placeholder,
  value,
  onChange,
}: {
  label: string;
  placeholder: string;
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-xs font-medium text-muted-foreground">{label}</span>
      <input
        className="h-9 rounded-md border border-border bg-white px-3 text-sm text-brand-ink outline-none focus:border-accent"
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
    </label>
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
