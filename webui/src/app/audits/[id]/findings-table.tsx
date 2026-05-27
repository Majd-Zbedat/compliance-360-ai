"use client";

import { useMemo, useState } from "react";
import { ChevronRight, Filter } from "lucide-react";
import { RiskBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { Clause, Finding } from "@/lib/api";

const RISK_ORDER: Record<string, number> = { High: 0, Medium: 1, Low: 2 };

export function FindingsTable({
  findings,
  clauses,
}: {
  findings: Finding[];
  clauses: Clause[];
}) {
  const [riskFilter, setRiskFilter] = useState<string | null>(null);
  const [selected, setSelected] = useState<{
    finding: Finding;
    clause?: Clause;
  } | null>(null);

  const clauseById = useMemo(() => {
    const map = new Map<string, Clause>();
    for (const c of clauses) map.set(c.id, c);
    return map;
  }, [clauses]);

  const filtered = useMemo(() => {
    const items = riskFilter ? findings.filter((f) => f.risk === riskFilter) : findings;
    return [...items].sort(
      (a, b) => (RISK_ORDER[a.risk] ?? 9) - (RISK_ORDER[b.risk] ?? 9),
    );
  }, [findings, riskFilter]);

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 text-xs">
        <Filter className="h-3.5 w-3.5 text-muted-foreground" />
        <span className="text-muted-foreground">Filter:</span>
        {(["High", "Medium", "Low"] as const).map((r) => (
          <button
            key={r}
            onClick={() => setRiskFilter(riskFilter === r ? null : r)}
            className={
              "rounded-full border px-2 py-0.5 transition-colors " +
              (riskFilter === r
                ? "border-primary bg-primary text-primary-foreground"
                : "border-border text-muted-foreground hover:bg-muted")
            }
          >
            {r}
          </button>
        ))}
        {riskFilter && (
          <button
            onClick={() => setRiskFilter(null)}
            className="text-muted-foreground underline"
          >
            clear
          </button>
        )}
      </div>

      {filtered.length === 0 ? (
        <p className="py-8 text-center text-sm text-muted-foreground">
          No findings match the current filter.
        </p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Clause</TableHead>
              <TableHead>Type</TableHead>
              <TableHead>Verdict</TableHead>
              <TableHead>Risk</TableHead>
              <TableHead>Cited regulation</TableHead>
              <TableHead>Conf.</TableHead>
              <TableHead className="w-8"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filtered.map((f, idx) => {
              const clause = clauseById.get(f.contract_clause_id);
              return (
                <TableRow
                  key={`${f.contract_clause_id}-${idx}`}
                  className="cursor-pointer"
                  onClick={() => setSelected({ finding: f, clause })}
                >
                  <TableCell className="max-w-xs truncate font-medium">
                    {clause?.section || f.contract_clause_id}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {clause?.clause_type || "—"}
                  </TableCell>
                  <TableCell className="capitalize">{f.verdict.replace("_", " ")}</TableCell>
                  <TableCell>
                    <RiskBadge risk={f.risk} />
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {f.matched_regulatory_source ? (
                      <>
                        {f.matched_regulatory_source} {f.matched_regulatory_article}
                      </>
                    ) : (
                      "—"
                    )}
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {(f.confidence * 100).toFixed(0)}%
                  </TableCell>
                  <TableCell>
                    <ChevronRight className="h-4 w-4 text-muted-foreground" />
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      )}

      <Sheet open={selected !== null} onOpenChange={(o) => !o && setSelected(null)}>
        <SheetContent>
          {selected && (
            <FindingDrawer finding={selected.finding} clause={selected.clause} />
          )}
        </SheetContent>
      </Sheet>
    </div>
  );
}

function FindingDrawer({ finding, clause }: { finding: Finding; clause?: Clause }) {
  const justification =
    finding.safe_justification && finding.safe_justification !== finding.justification
      ? finding.safe_justification
      : finding.justification;
  const wasRewritten =
    finding.safe_justification && finding.safe_justification !== finding.justification;
  return (
    <>
      <SheetHeader>
        <SheetTitle>{clause?.section || finding.contract_clause_id}</SheetTitle>
        <SheetDescription>
          Risk <RiskBadge risk={finding.risk} /> · verdict <em>{finding.verdict}</em> ·
          confidence {(finding.confidence * 100).toFixed(0)}%
        </SheetDescription>
      </SheetHeader>

      <section className="space-y-4 text-sm">
        <div>
          <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Contract clause
          </div>
          <div className="rounded-md border border-border bg-muted/40 p-3 leading-relaxed">
            {clause?.text || "Clause text unavailable."}
          </div>
          {clause?.page != null && (
            <div className="mt-1 text-xs text-muted-foreground">Page {clause.page}</div>
          )}
        </div>

        <div>
          <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Cited regulation
          </div>
          {finding.matched_regulatory_clause_id ? (
            <div className="rounded-md border border-border bg-card p-3">
              <div className="font-medium">
                {finding.matched_regulatory_source} {finding.matched_regulatory_article}
              </div>
              <div className="mt-1 text-xs text-muted-foreground">
                id: <code>{finding.matched_regulatory_clause_id}</code>
              </div>
            </div>
          ) : (
            <p className="text-muted-foreground">No matching regulation retrieved.</p>
          )}
        </div>

        <div>
          <div className="mb-1 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Analyst justification
            {wasRewritten && (
              <span className="rounded-full bg-amber-100 px-1.5 py-0.5 text-[10px] font-semibold text-amber-800">
                rewritten by guardrail
              </span>
            )}
          </div>
          <div className="rounded-md border border-border bg-muted/40 p-3 leading-relaxed">
            {justification}
          </div>
          {wasRewritten && (
            <details className="mt-2 text-xs text-muted-foreground">
              <summary className="cursor-pointer">View original (pre-guardrail) text</summary>
              <div className="mt-1 rounded-md border border-dashed border-border p-2">
                {finding.justification}
              </div>
            </details>
          )}
        </div>
      </section>
    </>
  );
}
