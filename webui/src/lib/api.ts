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
  review_status?: string | null;  // Approved | Pending | Rejected | null
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
  recommendation?: string | null;
  clause_section?: string | null;
  clause_excerpt?: string | null;
  clause_type?: string | null;
  regulatory_title?: string | null;
  regulatory_excerpt?: string | null;
}

export interface ContractMetadata {
  contract_number?: string | null;
  effective_date?: string | null;
  expiry_date?: string | null;
  jurisdiction?: string | null;
  contract_value?: string | null;
  payment_terms?: string | null;
  contract_manager?: string | null;
  status?: string | null;
  party_a?: string | null;
  party_a_address?: string | null;
  party_a_regulated_by?: string | null;
  party_a_registration?: string | null;
  party_a_lei?: string | null;
  party_b?: string | null;
  party_b_address?: string | null;
  party_b_regulated_by?: string | null;
  party_b_registration?: string | null;
  party_b_lei?: string | null;
  party_b_abn?: string | null;
  term?: string | null;
  governing_law?: string | null;
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
  review_status?: string | null;
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
  contract_metadata?: ContractMetadata | null;
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
  regulation_count?: number;
  regulations_uploaded?: number;
  pending_reviews?: number;
  compliance_score?: number;
  high_risk_delta_7d?: number;
  pending_reviews_last_7d?: number;
  compliance_score_delta?: number;
  monthly_compliance?: { month: string; score: number }[];
  last_audit_at?: string | null;
}

export interface Regulation {
  id: string;
  source: string;
  article: string;
  title?: string | null;
  text: string;
  tags: string[];
}

export interface AddRegulationResponse {
  added: number;
  total_indexed: number;
  source: string;
  ocr_used: boolean;
  warning?: string | null;
}

export interface ChatSource {
  id: string;
  source: string;
  article: string;
  title?: string | null;
  text: string;
  score: number;
}

export interface PortfolioHit {
  id: string;
  category: string;
  title?: string | null;
  preview: string;
  risk_level?: string | null;
  compliance_standard?: string | null;
}

export interface PortfolioStats {
  category: string;
  label: string;
  total_contracts: number;
  active_contracts?: number | null;
  by_status: Record<string, number>;
  by_risk: Record<string, number>;
  summary_kpis: Record<string, string>;
}

export interface ChatResponse {
  question: string;
  answer: string;
  sources: ChatSource[];
  portfolio_hits?: PortfolioHit[];
  portfolio_stats?: PortfolioStats | null;
  intent?: string;
  refused?: boolean;
}

export interface CreateAuditResponse {
  audit_id: string;
  status: string;
  overall_risk: string;
  rejected: boolean;
  rejection_reason?: string | null;
}

export interface RegulationRef {
  source: string;
  name: string;
}

export interface ContractCategory {
  id: string;
  label: string;
  description: string;
  source_file: string;
  contract_count: number;
  industry_sector?: string | null;
  regulatory_focus?: string | null;
  default_jurisdiction?: string | null;
  default_contract_type?: string | null;
  regulations: RegulationRef[];
  regulation_sources: string[];
}

export interface ContractSummary {
  id: string;
  external_id?: string | null;
  category: string;
  title?: string | null;
  source_file?: string | null;
  risk_level?: string | null;
  compliance_standard?: string | null;
  preview: string;
}

export interface ContractListResponse {
  category: string;
  total: number;
  items: ContractSummary[];
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
  contractCategories: () => request<ContractCategory[]>("/contracts/categories"),
  listContracts: (category: string, q?: string, limit = 100) => {
    const params = new URLSearchParams({ category, limit: String(limit) });
    if (q) params.set("q", q);
    return request<ContractListResponse>(`/contracts?${params.toString()}`);
  },
  regulations: (source?: string, q?: string) => {
    const params = new URLSearchParams();
    if (source) params.set("source", source);
    if (q) params.set("q", q);
    const qs = params.toString();
    return request<Regulation[]>(`/regulations${qs ? `?${qs}` : ""}`);
  },
  chat: (payload: {
    question: string;
    top_k?: number;
    sources?: string[];
    contract_category?: string;
    audit_id?: string;
  }) =>
    request<ChatResponse>("/chat", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  portfolioStats: (category: string) =>
    request<PortfolioStats>(`/contracts/portfolio-stats?category=${encodeURIComponent(category)}`),
  createAudit: (payload: {
    filename?: string;
    document_b64?: string;
    parties?: string[];
    jurisdiction?: string;
    contract_type?: string;
    requester?: string;
    industry_sector?: string;
    regulatory_focus?: string;
    contract_category?: string;
    dataset_contract_id?: string;
    regulatory_sources?: string[];
  }) =>
    request<CreateAuditResponse>("/audits", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateReviewStatus: (auditId: string, reviewStatus: "Approved" | "Pending" | "Rejected") =>
    request<{ id: string; review_status: string }>(`/audits/${auditId}/status`, {
      method: "PATCH",
      body: JSON.stringify({ review_status: reviewStatus }),
    }),
  deleteAudit: (auditId: string) =>
    request<{ id: string; deleted: boolean }>(`/audits/${auditId}`, {
      method: "DELETE",
    }),
  addRegulation: (payload: {
    source: string;
    article?: string;
    title?: string;
    text?: string;
    document_b64?: string;
    filename?: string;
    tags?: string[];
  }) =>
    request<AddRegulationResponse>("/regulations", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};
