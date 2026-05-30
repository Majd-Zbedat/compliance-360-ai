import {
  AlertTriangle,
  BookOpen,
  CheckCircle2,
  Lightbulb,
  ShieldAlert,
  ShieldCheck,
  ShieldX,
  Wrench,
} from "lucide-react";
import type { AuditDetail } from "@/lib/api";

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

export function ComplianceReportCard({ audit }: { audit: AuditDetail }) {
  const rejected = audit.status === "Rejected";
  const review = audit.status === "Review";
  const theme = riskTheme(audit.overall_risk);

  const sortedFindings = [...audit.findings].sort(
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

  const clauseSection = (clauseId: string) =>
    audit.clauses.find((c) => c.id === clauseId)?.section || clauseId;

  const corrections = sortedFindings
    .filter((f) => f.verdict !== "compliant" && f.recommendation)
    .slice(0, 5);

  const citations = dedupeCitations(audit.findings);

  const RiskIcon =
    audit.overall_risk === "High"
      ? ShieldX
      : audit.overall_risk === "Medium"
        ? ShieldAlert
        : ShieldCheck;

  return (
    <div className="overflow-hidden rounded-xl border border-border bg-card shadow-sm">
      {/* confirmation strip */}
      <div className="flex items-center gap-2 border-b border-border bg-muted/40 px-5 py-2.5 text-xs font-medium text-muted-foreground">
        <CheckCircle2 size={14} className="text-accent" />
        Report received · analysed against your regulation library
      </div>

      <div className="space-y-6 p-5">
        {/* header */}
        <div className="flex items-start gap-3">
          <div
            className="flex h-12 w-12 shrink-0 items-center justify-center rounded-lg"
            style={{ backgroundColor: theme.bg, color: theme.text }}
          >
            <RiskIcon size={24} />
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="truncate text-lg font-bold text-primary">
                {audit.contract_type || "Compliance Audit"}
              </h3>
              <span
                className="rounded-full px-2.5 py-0.5 text-xs font-semibold"
                style={{ backgroundColor: theme.bg, color: theme.text }}
              >
                {rejected
                  ? "Rejected"
                  : review
                    ? "Needs review"
                    : `${audit.overall_risk} Risk`}
              </span>
            </div>
            <p className="mt-0.5 truncate text-sm text-muted-foreground">{audit.filename}</p>
          </div>
        </div>

        {/* metadata grid */}
        <div className="flex flex-wrap gap-x-8 gap-y-3 text-sm">
          <Meta label="Jurisdiction" value={audit.jurisdiction || "—"} />
          <Meta
            label="Parties"
            value={audit.parties.length ? audit.parties.join(", ") : "—"}
          />
          <Meta label="Findings" value={String(audit.findings.length)} />
          {avgConfidence != null && (
            <Meta label="Avg. confidence" value={`${avgConfidence}%`} />
          )}
        </div>

        {rejected ? (
          <InsightBox tone="danger" title="Why this was rejected">
            {audit.rejection_reason ||
              "The submission was rejected by the input guardrail before analysis."}
          </InsightBox>
        ) : (
          <>
            {/* key findings */}
            {sortedFindings.length > 0 && (
              <Section icon={<AlertTriangle size={14} />} title="Key findings">
                <ul className="space-y-2">
                  {sortedFindings.slice(0, 6).map((f, i) => {
                    const t = riskTheme(f.risk);
                    return (
                      <li key={i} className="flex gap-2.5 text-[13px] leading-relaxed">
                        <span
                          className="mt-1.5 h-2 w-2 shrink-0 rounded-full"
                          style={{ backgroundColor: t.ring }}
                        />
                        <span>
                          <span className="font-semibold text-brand-ink">
                            {clauseSection(f.contract_clause_id)}
                          </span>{" "}
                          <span
                            className="rounded px-1.5 py-0.5 text-[11px] font-medium"
                            style={{ backgroundColor: t.bg, color: t.text }}
                          >
                            {f.risk} · {f.verdict.replace("_", " ")}
                          </span>
                          {f.matched_regulatory_source && (
                            <span className="text-muted-foreground">
                              {" "}
                              — {f.matched_regulatory_source} {f.matched_regulatory_article}
                            </span>
                          )}
                        </span>
                      </li>
                    );
                  })}
                </ul>
              </Section>
            )}

            {/* recommended corrections */}
            {corrections.length > 0 && (
              <Section icon={<Wrench size={14} />} title="Recommended corrections">
                <ul className="space-y-2">
                  {corrections.map((f, i) => (
                    <li key={i} className="flex gap-2.5 text-[13px] leading-relaxed">
                      <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />
                      <span>
                        <span className="font-medium text-brand-ink">
                          {clauseSection(f.contract_clause_id)}:
                        </span>{" "}
                        <span className="text-muted-foreground">{f.recommendation}</span>
                      </span>
                    </li>
                  ))}
                </ul>
              </Section>
            )}

            {/* cited regulations */}
            {citations.length > 0 && (
              <Section icon={<BookOpen size={14} />} title="Regulations triggering risk">
                <ul className="space-y-1.5">
                  {citations.map((c, i) => (
                    <li key={i} className="flex gap-2.5 text-[13px] text-muted-foreground">
                      <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-muted-foreground/40" />
                      <span>
                        <span className="font-medium text-brand-ink">
                          {c.source} {c.article}
                        </span>
                        {c.count > 1 && (
                          <span className="text-muted-foreground"> · {c.count} clauses</span>
                        )}
                      </span>
                    </li>
                  ))}
                </ul>
              </Section>
            )}

            {/* insight box */}
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
                  {audit.findings.length} finding
                  {audit.findings.length !== 1 ? "s" : ""} — <strong>{high} High</strong>,{" "}
                  {medium} Medium, {low} Low. Overall risk is{" "}
                  <strong>{audit.overall_risk}</strong>
                  {high > 0
                    ? ". Address the High-risk clauses above before signing."
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

function dedupeCitations(findings: AuditDetail["findings"]) {
  const map = new Map<string, { source: string; article: string; count: number }>();
  for (const f of findings) {
    if (!f.matched_regulatory_source) continue;
    const key = `${f.matched_regulatory_source} ${f.matched_regulatory_article || ""}`.trim();
    const existing = map.get(key);
    if (existing) existing.count += 1;
    else
      map.set(key, {
        source: f.matched_regulatory_source,
        article: f.matched_regulatory_article || "",
        count: 1,
      });
  }
  return Array.from(map.values()).slice(0, 8);
}

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <div className="text-[11px] uppercase tracking-wide text-muted-foreground">{label}</div>
      <div className="font-medium text-brand-ink">{value}</div>
    </div>
  );
}

function Section({
  icon,
  title,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <div className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        {icon}
        {title}
      </div>
      {children}
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
      <p className="text-[13px] leading-relaxed text-brand-ink">{children}</p>
    </div>
  );
}
