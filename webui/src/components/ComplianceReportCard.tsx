"use client";

import { useState } from "react";
import {
  AlertTriangle,
  Building2,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Lightbulb,
  ShieldAlert,
  ShieldCheck,
  ShieldX,
  Wrench,
} from "lucide-react";
import type { AuditDetail, Finding, ContractMetadata } from "@/lib/api";

const RISK_ORDER: Record<string, number> = { High: 0, Medium: 1, Low: 2 };

function riskTheme(risk: string): { bg: string; text: string; ring: string } {
  switch (risk) {
    case "High":
      return { bg: "#FEF2F2", text: "#991B1B", ring: "#EF4444" };
    case "Medium":
      return { bg: "#FFF7ED", text: "#92400E", ring: "#F59E0B" };
    case "Low":
      return { bg: "#F0F9E8", text: "#2D6A0A", ring: "#86BC25" };
    default:
      return { bg: "#EFF6FF", text: "#1D4ED8", ring: "#3B82F6" };
  }
}

function clauseLabel(f: Finding, audit: AuditDetail): string {
  const section =
    f.clause_section ||
    audit.clauses.find((c) => c.id === f.contract_clause_id)?.section;
  if (section && section !== "clause_1") return section;
  const cid = f.contract_clause_id;
  if (cid && cid !== "clause_1") return cid;
  return "Contract clause";
}

/* ─── Finding row ─────────────────────────────────────────────────────────── */

function FindingRow({ f, audit }: { f: Finding; audit: AuditDetail }) {
  const [open, setOpen] = useState(false);
  const t = riskTheme(f.risk);
  const label = clauseLabel(f, audit);

  return (
    <li className="rounded-lg border border-border bg-card overflow-hidden">
      <button
        type="button"
        className="flex w-full items-start gap-3 px-4 py-3 text-left hover:bg-muted/30 transition-colors"
        onClick={() => setOpen((v) => !v)}
      >
        <span
          className="mt-1 h-2.5 w-2.5 shrink-0 rounded-full"
          style={{ backgroundColor: t.ring }}
        />
        <div className="min-w-0 flex-1 space-y-0.5">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-semibold text-primary text-[13px]">{label}</span>
            <span
              className="rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide"
              style={{ backgroundColor: t.bg, color: t.text }}
            >
              {f.risk}
            </span>
            {f.matched_regulatory_source && (
              <span className="text-[11px] text-muted-foreground">
                {f.matched_regulatory_source}
                {f.matched_regulatory_article ? ` · ${f.matched_regulatory_article}` : ""}
              </span>
            )}
          </div>
          {!open && f.justification && (
            <p className="text-[12px] text-muted-foreground line-clamp-1">{f.justification}</p>
          )}
        </div>
        {open ? (
          <ChevronUp size={14} className="shrink-0 mt-1 text-muted-foreground" />
        ) : (
          <ChevronDown size={14} className="shrink-0 mt-1 text-muted-foreground" />
        )}
      </button>

      {open && (
        <div className="border-t border-border divide-y divide-border/60">
          <div className="px-4 py-3 space-y-1">
            <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
              Gap identified
            </p>
            <p className="text-[13px] text-primary leading-relaxed">{f.justification}</p>
          </div>
          {f.recommendation && f.verdict !== "compliant" && (
            <div className="px-4 py-3 space-y-1">
              <p className="text-[10px] font-semibold uppercase tracking-wide text-accent flex items-center gap-1">
                <Wrench size={10} />
                Recommended correction
              </p>
              <p className="text-[13px] text-muted-foreground leading-relaxed">
                {f.recommendation}
              </p>
            </div>
          )}
        </div>
      )}
    </li>
  );
}

/* ─── Party card ──────────────────────────────────────────────────────────── */

function PartyCard({
  role,
  name,
  address,
  regulatedBy,
  registration,
  lei,
  abn,
}: {
  role: string;
  name?: string | null;
  address?: string | null;
  regulatedBy?: string | null;
  registration?: string | null;
  lei?: string | null;
  abn?: string | null;
}) {
  if (!name) return null;
  return (
    <div className="flex-1 min-w-[220px] rounded-lg border border-border bg-card p-4 space-y-2">
      <div className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
        {role}
      </div>
      <div className="flex items-start gap-2">
        <Building2 size={15} className="mt-0.5 shrink-0 text-accent" />
        <p className="text-[13px] font-semibold text-primary leading-snug">{name}</p>
      </div>
      {address && (
        <p className="text-[12px] text-muted-foreground">{address}</p>
      )}
      {regulatedBy && (
        <p className="text-[11px] text-muted-foreground">
          <span className="font-medium">Regulated by:</span> {regulatedBy}
        </p>
      )}
      {registration && (
        <p className="text-[11px] text-muted-foreground">
          <span className="font-medium">Registration No.:</span> {registration}
        </p>
      )}
      <div className="flex flex-wrap gap-x-4 gap-y-0.5">
        {lei && (
          <p className="text-[11px] text-muted-foreground font-mono">
            <span className="font-sans font-medium not-italic">LEI:</span> {lei}
          </p>
        )}
        {abn && (
          <p className="text-[11px] text-muted-foreground font-mono">
            <span className="font-sans font-medium not-italic">ABN:</span> {abn}
          </p>
        )}
      </div>
    </div>
  );
}

/* ─── Main component ──────────────────────────────────────────────────────── */

export function ComplianceReportCard({ audit }: { audit: AuditDetail }) {
  const rejected = audit.status === "Rejected";
  const review = audit.status === "Review";
  const theme = riskTheme(audit.overall_risk);

  // Only surface actual compliance gaps (High / Medium). Low-risk clauses are
  // compliant/operational and are summarised separately rather than listed.
  const gapFindings = audit.findings.filter(
    (f) => f.risk === "High" || f.risk === "Medium",
  );
  const sortedFindings = [...gapFindings].sort(
    (a, b) => (RISK_ORDER[a.risk] ?? 9) - (RISK_ORDER[b.risk] ?? 9),
  );

  const high = audit.findings.filter((f) => f.risk === "High").length;
  const medium = audit.findings.filter((f) => f.risk === "Medium").length;
  const low = audit.findings.filter((f) => f.risk === "Low").length;

  const avgConfidence =
    audit.findings.length > 0
      ? Math.round(
          (audit.findings.reduce((s, f) => s + (f.confidence || 0), 0) /
            audit.findings.length) *
            100,
        )
      : null;

  const meta: ContractMetadata | null | undefined = audit.contract_metadata;

  const RiskIcon =
    audit.overall_risk === "High"
      ? ShieldX
      : audit.overall_risk === "Medium"
        ? ShieldAlert
        : ShieldCheck;

  const hasContractTable =
    meta &&
    (meta.contract_number ||
      meta.effective_date ||
      meta.expiry_date ||
      meta.contract_value ||
      meta.status ||
      meta.contract_manager ||
      meta.payment_terms ||
      meta.jurisdiction ||
      meta.governing_law);

  const hasParties = meta && (meta.party_a || meta.party_b);

  return (
    <div className="overflow-hidden rounded-xl border border-border bg-card shadow-sm">
      {/* Status bar */}
      <div className="flex items-center gap-2 border-b border-border bg-muted/40 px-5 py-2.5 text-xs font-medium text-muted-foreground">
        <CheckCircle2 size={14} className="text-accent" />
        Report received · analysed against your regulation library
      </div>

      <div className="p-5 space-y-5">
        {/* Title */}
        <div className="flex items-start gap-3">
          <div
            className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg"
            style={{ backgroundColor: theme.bg, color: theme.text }}
          >
            <RiskIcon size={22} />
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="truncate text-base font-bold text-primary">
                {audit.contract_type || "Compliance Audit"}
              </h3>
              <span
                className="rounded-full px-2.5 py-0.5 text-xs font-semibold"
                style={{ backgroundColor: theme.bg, color: theme.text }}
              >
                {rejected ? "Rejected" : review ? "Needs review" : `${audit.overall_risk} Risk`}
              </span>
            </div>
            <p className="mt-0.5 truncate text-xs text-muted-foreground">{audit.filename}</p>
          </div>
        </div>

        {/* Contract details table */}
        {hasContractTable && (
          <div className="rounded-lg border border-border overflow-hidden">
            <div className="bg-muted/50 px-4 py-2 border-b border-border text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
              Contract details
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 divide-x divide-y divide-border/60 bg-border">
              {meta?.contract_number && (
                <Cell label="Contract ID" value={meta.contract_number} />
              )}
              {meta?.status && (
                <Cell label="Status" value={meta.status} />
              )}
              {meta?.effective_date && (
                <Cell label="Effective date" value={meta.effective_date} />
              )}
              {meta?.expiry_date && (
                <Cell label="Expiry date" value={meta.expiry_date} />
              )}
              {meta?.contract_value && (
                <Cell label="Contract value" value={meta.contract_value} />
              )}
              {meta?.contract_manager && (
                <Cell label="Contract manager" value={meta.contract_manager} />
              )}
              {meta?.payment_terms && (
                <Cell label="Payment terms" value={meta.payment_terms} />
              )}
              {(audit.jurisdiction || meta?.jurisdiction) && (
                <Cell
                  label="Jurisdiction"
                  value={audit.jurisdiction || meta?.jurisdiction || ""}
                />
              )}
              {meta?.governing_law && meta.governing_law !== (audit.jurisdiction || meta?.jurisdiction) && (
                <Cell label="Governing law" value={meta.governing_law} />
              )}
            </div>
          </div>
        )}

        {/* Contracting parties */}
        {hasParties && (
          <div>
            <div className="mb-2 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
              Contracting parties
            </div>
            <div className="flex flex-wrap gap-3">
              <PartyCard
                role="Party A — Engaging institution"
                name={meta?.party_a}
                address={meta?.party_a_address}
                regulatedBy={meta?.party_a_regulated_by}
                registration={meta?.party_a_registration}
                lei={meta?.party_a_lei}
              />
              <PartyCard
                role="Party B — Service provider"
                name={meta?.party_b}
                address={meta?.party_b_address}
                regulatedBy={meta?.party_b_regulated_by}
                registration={meta?.party_b_registration}
                lei={meta?.party_b_lei}
                abn={meta?.party_b_abn}
              />
            </div>
          </div>
        )}

        {/* Summary counts */}
        <div className="flex flex-wrap gap-x-6 gap-y-2 text-sm">
          <MiniMeta
            label="Gaps"
            value={`${high + medium} (${high} High · ${medium} Medium)`}
          />
          {low > 0 && (
            <MiniMeta label="Compliant clauses" value={`${low}`} />
          )}
          {avgConfidence != null && (
            <MiniMeta label="Avg. confidence" value={`${avgConfidence}%`} />
          )}
        </div>

        {/* Findings */}
        {rejected ? (
          <InsightBox tone="danger" title="Why this was rejected">
            {audit.rejection_reason ||
              "The submission was rejected by the input guardrail before analysis."}
          </InsightBox>
        ) : (
          <>
            {sortedFindings.length > 0 && (
              <div>
                <div className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  <AlertTriangle size={13} />
                  Key findings — click to expand gap &amp; correction
                </div>
                <ul className="space-y-2">
                  {sortedFindings.slice(0, 10).map((f, i) => (
                    <FindingRow key={i} f={f} audit={audit} />
                  ))}
                </ul>
              </div>
            )}

            <InsightBox
              tone={
                audit.overall_risk === "High"
                  ? "danger"
                  : audit.overall_risk === "Medium"
                    ? "warning"
                    : "ok"
              }
              title="Compliance insight"
            >
              {review && (
                <>
                  This report was <strong>flagged for human review</strong> by the output
                  guardrail.{" "}
                </>
              )}
              {audit.findings.length === 0 ? (
                <>No clause-level findings were generated for this contract.</>
              ) : (
                <>
                  <strong>{high + medium} compliance gap{high + medium !== 1 ? "s" : ""}</strong>{" "}
                  ({high} High, {medium} Medium) across {audit.findings.length} analysed clause
                  {audit.findings.length !== 1 ? "s" : ""}; {low} compliant. Overall risk is{" "}
                  <strong>{audit.overall_risk}</strong>
                  {high > 0
                    ? ". Address the High-risk clauses before signing."
                    : medium > 0
                      ? ". Review the Medium-risk clauses with the counterparty."
                      : ". No material compliance gaps detected."}
                </>
              )}
            </InsightBox>
          </>
        )}
      </div>
    </div>
  );
}

/* ─── Helpers ─────────────────────────────────────────────────────────────── */

function Cell({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-card px-4 py-3">
      <div className="text-[10px] uppercase tracking-wide text-muted-foreground">{label}</div>
      <div className="mt-0.5 text-[13px] font-medium text-primary" title={value}>
        {value}
      </div>
    </div>
  );
}

function MiniMeta({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span className="text-[11px] uppercase tracking-wide text-muted-foreground mr-1">
        {label}
      </span>
      <span className="text-[13px] font-medium text-primary">{value}</span>
    </div>
  );
}

function InsightBox({
  tone,
  title,
  children,
}: {
  tone: "ok" | "warning" | "danger";
  title: string;
  children: React.ReactNode;
}) {
  const themes = {
    ok: { bg: "#F0F9E8", border: "#86BC2555", text: "#2D6A0A" },
    warning: { bg: "#FFF7ED", border: "#F59E0B55", text: "#92400E" },
    danger: { bg: "#FEF2F2", border: "#EF444455", text: "#991B1B" },
  }[tone];
  return (
    <div
      className="rounded-lg border p-4"
      style={{ backgroundColor: themes.bg, borderColor: themes.border }}
    >
      <div
        className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide"
        style={{ color: themes.text }}
      >
        <Lightbulb size={13} />
        {title}
      </div>
      <p className="text-[13px] leading-relaxed text-primary">{children}</p>
    </div>
  );
}
