/**
 * API DTOs — mirrors packages/contracts/openapi.json (the frozen contract).
 * Field names/shapes must match the backend schemas exactly; the contract
 * test on the API side guards drift.
 */

export type RunStatus = "queued" | "running" | "succeeded" | "partial" | "failed";
export type Verdict = "COMPLIANT" | "VIOLATIONS_FOUND" | "INSUFFICIENT_EVIDENCE";
export type RiskLevel = "HIGH" | "MEDIUM" | "LOW";
export type CandidateSource = "vector" | "citation";

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface OrgOut {
  id: number;
  name: string;
  home_jurisdiction: string;
  created_at: string;
}

export interface Coverage {
  violation: number;
  compliant: number;
  insufficient_evidence: number;
  error: number;
}

export interface AuditRunOut {
  id: number;
  status: RunStatus;
  verdict: Verdict | null;
  coverage: Coverage | null;
  stale: boolean;
  jurisdiction: string;
  as_of_date: string;
  policy_id: number | null;
  policy_version_id: number | null;
  model: string | null;
  total_tokens: number;
  cost_usd: number | null;
  error: string | null;
  created_at: string;
  finished_at: string | null;
}

export interface AuditCreate {
  policy_id?: number;
  policy_text?: string;
  jurisdiction: string;
  as_of_date?: string;
}

export interface FindingOut {
  id: number;
  clause_index: number;
  risk_level: RiskLevel;
  offending_policy_text: string;
  legal_rule_text: string;
  citation: string;
  grounding_quote: string;
  rationale: string;
  suggested_fix: string;
  source_chunk_id: number | null;
  source_document_id: number | null;
  source_url: string;
  confidence: number;
  needs_review: boolean;
}

