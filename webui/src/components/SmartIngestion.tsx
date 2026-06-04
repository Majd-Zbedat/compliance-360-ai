"use client";

import { useCallback, useRef, useState } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  FileText,
  Loader2,
  RotateCcw,
  Upload,
  X,
} from "lucide-react";
import { api, type AuditDetail } from "@/lib/api";
import { ComplianceReportCard } from "@/components/ComplianceReportCard";

type Phase = "idle" | "reading" | "submitting";

const CONTRACT_TYPES = [
  { value: "", label: "Select contract type…" },
  { value: "MSA", label: "Master Services Agreement (MSA)" },
  { value: "DPA", label: "Data Processing Agreement (DPA)" },
  { value: "NDA", label: "Non-Disclosure Agreement (NDA)" },
  { value: "Vendor / SaaS", label: "Vendor / SaaS Agreement" },
  { value: "Banking / Financial", label: "Banking / Financial Services" },
  { value: "Employment", label: "Employment / HR" },
  { value: "Other", label: "Other" },
];

const JURISDICTIONS = [
  { value: "", label: "Select jurisdiction…" },
  { value: "EU / GDPR", label: "EU / GDPR" },
  { value: "US Federal", label: "US Federal" },
  { value: "UK", label: "United Kingdom" },
  { value: "Israel", label: "Israel" },
  { value: "Global / Multi-jurisdiction", label: "Global / Multi-jurisdiction" },
  { value: "Other", label: "Other" },
];

const INDUSTRY_SECTORS = [
  { value: "", label: "Select industry (optional)…" },
  { value: "Banking & Finance", label: "Banking & Finance" },
  { value: "Cybersecurity & IT", label: "Cybersecurity & IT" },
  { value: "Healthcare", label: "Healthcare" },
  { value: "AI / Machine Learning", label: "AI / Machine Learning" },
  { value: "General / Cross-industry", label: "General / Cross-industry" },
  { value: "Other", label: "Other" },
];

const REGULATORY_FOCUS = [
  { value: "", label: "Auto — full regulation library" },
  { value: "Data Privacy (GDPR, Privacy Controls)", label: "Data Privacy (GDPR, Privacy Controls)" },
  { value: "Banking (SOX, PCI DSS, AML/KYC, Basel III)", label: "Banking (SOX, PCI DSS, AML/KYC, Basel III)" },
  { value: "Cybersecurity (NIST CSF, SOC 2, ISO 27001)", label: "Cybersecurity (NIST CSF, SOC 2, ISO 27001)" },
  { value: "Healthcare (HIPAA)", label: "Healthcare (HIPAA)" },
  { value: "AI Governance (ISO 42001, GDPR)", label: "AI Governance (ISO 42001, GDPR)" },
  { value: "Other", label: "Other" },
];

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

export function SmartIngestion() {
  const [isDragging, setIsDragging] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [phase, setPhase] = useState<Phase>("idle");
  const [error, setError] = useState<string | null>(null);
  const [contractType, setContractType] = useState("");
  const [contractTypeOther, setContractTypeOther] = useState("");
  const [jurisdiction, setJurisdiction] = useState("");
  const [jurisdictionOther, setJurisdictionOther] = useState("");
  const [industrySector, setIndustrySector] = useState("");
  const [industrySectorOther, setIndustrySectorOther] = useState("");
  const [regulatoryFocus, setRegulatoryFocus] = useState("");
  const [regulatoryFocusOther, setRegulatoryFocusOther] = useState("");
  const [result, setResult] = useState<AuditDetail | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const resolvedContractType =
    contractType === "Other" ? contractTypeOther.trim() : contractType;
  const resolvedJurisdiction =
    jurisdiction === "Other" ? jurisdictionOther.trim() : jurisdiction;
  const resolvedIndustry =
    industrySector === "Other"
      ? industrySectorOther.trim()
      : industrySector.trim();
  const resolvedRegulatory =
    regulatoryFocus === "Other"
      ? regulatoryFocusOther.trim()
      : regulatoryFocus.trim();

  const pickFile = (f: File | undefined | null) => {
    if (!f) return;
    setError(null);
    setFile(f);
  };

  const reset = () => {
    setResult(null);
    setFile(null);
    setError(null);
    setContractType("");
    setContractTypeOther("");
    setJurisdiction("");
    setJurisdictionOther("");
    setIndustrySector("");
    setIndustrySectorOther("");
    setRegulatoryFocus("");
    setRegulatoryFocusOther("");
    if (inputRef.current) inputRef.current.value = "";
  };

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    pickFile(e.dataTransfer.files?.[0]);
  }, []);

  const canSubmit = Boolean(file && resolvedContractType && resolvedJurisdiction);

  const run = async () => {
    if (!canSubmit || phase !== "idle" || !file) return;
    setError(null);
    try {
      setPhase("reading");
      const document_b64 = await fileToBase64(file);
      setPhase("submitting");
      const res = await api.createAudit({
        filename: file.name,
        document_b64,
        contract_type: resolvedContractType,
        jurisdiction: resolvedJurisdiction,
        industry_sector: resolvedIndustry || undefined,
        regulatory_focus: resolvedRegulatory || undefined,
      });
      const detail = await api.getAudit(res.audit_id);
      setResult(detail);
      if (typeof window !== "undefined") {
        sessionStorage.setItem("compliance360_last_audit_id", detail.id);
        window.dispatchEvent(
          new CustomEvent("compliance360-audit-complete", { detail: { auditId: detail.id } }),
        );
      }
      setPhase("idle");
    } catch (err: any) {
      setError(err?.message || "Failed to start audit");
      setPhase("idle");
    }
  };

  const busy = phase !== "idle";

  if (result) {
    return (
      <div>
        <div className="mb-4 flex items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <div className="h-5 w-0.5 rounded-full bg-accent" />
            <p className="text-xs font-semibold uppercase tracking-widest text-primary">
              Audit Feedback
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Link
              href={`/audits/${result.id}`}
              className="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-xs font-medium text-primary hover:bg-muted"
            >
              Open full report
              <ArrowRight size={13} />
            </Link>
            <button
              type="button"
              onClick={reset}
              className="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-xs font-medium text-white hover:bg-accent/90"
            >
              <RotateCcw size={13} />
              Analyze another
            </button>
          </div>
        </div>
        <ComplianceReportCard audit={result} />
      </div>
    );
  }

  return (
    <div>
      <div className="mb-4 flex items-center gap-2.5">
        <div className="h-5 w-0.5 rounded-full bg-accent" />
        <p className="text-xs font-semibold uppercase tracking-widest text-primary">
          Content Ingestion
        </p>
      </div>

      <div
        onDragOver={(e) => {
          e.preventDefault();
          setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
        onClick={() => !file && inputRef.current?.click()}
        className="select-none rounded-lg border-2 border-dashed transition-all"
        style={{
          borderColor: isDragging ? "#86BC25" : "#D1D5DB",
          backgroundColor: isDragging ? "#F4FAE8" : "#FAFAFA",
          cursor: file ? "default" : "pointer",
        }}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.txt"
          className="hidden"
          onChange={(e) => pickFile(e.target.files?.[0])}
        />

        <div className="flex min-h-[220px] flex-col items-center justify-center p-10 text-center">
          <div
            className="mb-4 flex h-14 w-14 items-center justify-center rounded-lg transition-all"
            style={{
              backgroundColor: isDragging ? "#D4F0A0" : "#EEF1F4",
              color: isDragging ? "#2D6A0A" : "#003B5C",
            }}
          >
            <FileText size={24} />
          </div>

          <p className="mb-1.5 text-base font-semibold text-primary">
            Upload a contract for analysis
          </p>
          <p className="mb-5 max-w-md text-sm text-[#9CA3AF]">
            Drag &amp; drop a contract PDF here, or click to browse. Fill in the
            fields below so the audit targets the right regulations.
          </p>

          {file && (
            <div className="mb-5 flex items-center gap-2.5 rounded border border-border bg-white px-3 py-2 text-sm text-brand-ink">
              <CheckCircle2 size={14} className="text-accent" />
              <span className="max-w-xs truncate text-left">{file.name}</span>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  setFile(null);
                  if (inputRef.current) inputRef.current.value = "";
                }}
                className="text-muted-foreground hover:text-destructive"
                aria-label="Remove file"
              >
                <X size={14} />
              </button>
            </div>
          )}

          <div
            className="mb-5 grid w-full max-w-xl grid-cols-1 gap-3 sm:grid-cols-2"
            onClick={(e) => e.stopPropagation()}
          >
            <SelectOrOtherField
              label="Contract type *"
              value={contractType}
              otherValue={contractTypeOther}
              onChange={setContractType}
              onOtherChange={setContractTypeOther}
              options={CONTRACT_TYPES}
              otherPlaceholder="Describe contract type…"
              required
            />
            <SelectOrOtherField
              label="Jurisdiction *"
              value={jurisdiction}
              otherValue={jurisdictionOther}
              onChange={setJurisdiction}
              onOtherChange={setJurisdictionOther}
              options={JURISDICTIONS}
              otherPlaceholder="e.g. Israel, California, Singapore…"
              required
            />
            <SelectOrOtherField
              label="Industry sector"
              value={industrySector}
              otherValue={industrySectorOther}
              onChange={setIndustrySector}
              onOtherChange={setIndustrySectorOther}
              options={INDUSTRY_SECTORS}
              otherPlaceholder="Describe industry…"
            />
            <SelectOrOtherField
              label="Regulations to prioritize"
              value={regulatoryFocus}
              otherValue={regulatoryFocusOther}
              onChange={setRegulatoryFocus}
              onOtherChange={setRegulatoryFocusOther}
              options={REGULATORY_FOCUS}
              otherPlaceholder="e.g. SOX + local banking law…"
            />
          </div>

          <button
            type="button"
            disabled={!canSubmit || busy}
            className="inline-flex items-center gap-2.5 rounded-md bg-accent px-5 py-2.5 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-50"
            onClick={(e) => {
              e.stopPropagation();
              run();
            }}
          >
            {busy ? <Loader2 size={14} className="animate-spin" /> : <Upload size={14} />}
            {phase === "reading"
              ? "Reading file…"
              : phase === "submitting"
                ? "Running Compliance 360…"
                : "Analyze contract"}
          </button>

          {!canSubmit && !busy && (
            <p className="mt-3 text-xs text-muted-foreground">
              Upload a PDF, select contract type and jurisdiction (or choose Other and type
              your value).
            </p>
          )}

          {error && (
            <div className="mt-4 flex max-w-xl items-start gap-2 rounded-md border border-destructive/30 bg-destructive/10 p-3 text-left text-sm text-destructive">
              <AlertTriangle size={16} className="mt-0.5 shrink-0" />
              <span>{error}</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function SelectOrOtherField({
  label,
  value,
  otherValue,
  onChange,
  onOtherChange,
  options,
  otherPlaceholder,
  required,
}: {
  label: string;
  value: string;
  otherValue: string;
  onChange: (v: string) => void;
  onOtherChange: (v: string) => void;
  options: { value: string; label: string }[];
  otherPlaceholder: string;
  required?: boolean;
}) {
  const isOther = value === "Other";

  return (
    <div className="flex flex-col gap-1 text-left">
      <span className="text-xs font-medium text-muted-foreground">{label}</span>
      <select
        className="h-9 rounded-md border border-border bg-white px-3 text-sm text-brand-ink outline-none focus:border-accent"
        value={value}
        onChange={(e) => {
          onChange(e.target.value);
          if (e.target.value !== "Other") onOtherChange("");
        }}
      >
        {options.map((o) => (
          <option key={o.value || "empty"} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
      {isOther && (
        <input
          type="text"
          className="h-9 rounded-md border border-border bg-white px-3 text-sm text-brand-ink outline-none focus:border-accent"
          placeholder={otherPlaceholder}
          value={otherValue}
          onChange={(e) => onOtherChange(e.target.value)}
          required={required}
          autoFocus
        />
      )}
    </div>
  );
}
