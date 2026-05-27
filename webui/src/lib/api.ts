/**
 * Typed client for the orchestrator REST API.
 *
 * The base URL is configured via NEXT_PUBLIC_API_BASE_URL so the same
 * build can target localhost during development and an EC2 IP / domain
 * in production without rebuilding.
 */

const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export interface AuditSummary {
  id: string;
  filename: string;
  status: string;
  overall_risk: string;
  findings_count: number;
  high_count: number;
  medium_count: number;
  low_count: number;
  created_at: string;
  requester?: string | null;
}

export interface Finding {
  contract_clause_id: string;
  matched_regulatory_clause_id?: string | null;
  matched_regulatory_source?: string | null;
  matched_regulatory_article?: string | null;
  verdict: string;
  risk: string;
  justification: string;
  confidence: number;
  safe_justification?: string | null;
}

export interface Clause {
  id: string;
  contract_id: string;
  section: string;
  text: string;
  clause_type: string;
  page?: number | null;
}

export interface AuditDetail {
  id: string;
  filename: string;
  status: string;
  overall_risk: string;
  parties: string[];
  jurisdiction?: string | null;
  contract_type?: string | null;
  requester?: string | null;
  clauses: Clause[];
  findings: Finding[];
  report_markdown?: string | null;
  safe_report_markdown?: string | null;
  input_guardrail_passed: boolean;
  output_guardrail_passed: boolean;
  rejection_reason?: string | null;
  created_at: string;
  updated_at: string;
}

export interface Stats {
  total_audits: number;
  audits_last_7d: number;
  high_risk_findings: number;
  medium_risk_findings: number;
  low_risk_findings: number;
  avg_findings_per_audit: number;
  rejection_rate: number;
  by_overall_risk: Record<string, number>;
}

export interface Regulation {
  id: string;
  source: string;
  article: string;
  title?: string | null;
  text: string;
  tags: string[];
}

export interface ChatSource {
  id: string;
  source: string;
  article: string;
  title?: string | null;
  text: string;
  score: number;
}

export interface ChatResponse {
  question: string;
  answer: string;
  sources: ChatSource[];
}

export interface CreateAuditResponse {
  audit_id: string;
  status: string;
  overall_risk: string;
  rejected: boolean;
  rejection_reason?: string | null;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    cache: "no-store",
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`API ${res.status} ${res.statusText}: ${body}`);
  }
  return (await res.json()) as T;
}

export const api = {
  listAudits: () => request<AuditSummary[]>("/audits"),
  getAudit: (id: string) => request<AuditDetail>(`/audits/${id}`),
  stats: () => request<Stats>("/audits/stats"),
  regulations: (source?: string, q?: string) => {
    const params = new URLSearchParams();
    if (source) params.set("source", source);
    if (q) params.set("q", q);
    const qs = params.toString();
    return request<Regulation[]>(`/regulations${qs ? `?${qs}` : ""}`);
  },
  chat: (payload: { question: string; top_k?: number; sources?: string[] }) =>
    request<ChatResponse>("/chat", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  createAudit: (payload: {
    filename: string;
    document_b64: string;
    parties?: string[];
    jurisdiction?: string;
    contract_type?: string;
    requester?: string;
  }) =>
    request<CreateAuditResponse>("/audits", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};
