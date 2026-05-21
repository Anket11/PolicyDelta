"use client";

import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseQueryResult,
} from "@tanstack/react-query";

import { apiFetch, pageQuery } from "@/lib/api/client";
import type {
  AuditCreate,
  AuditRunOut,
  ChunkOut,
  DocumentDetail,
  DocumentSummary,
  FindingOut,
  OrgOut,
  Page,
  PolicyOut,
  PolicySummary,
  PolicyVersionOut,
  RegulatorySearchRequest,
  RegulatorySearchResponse,
} from "@/lib/api/types";
import { AUDIT_POLL_INTERVAL_MS, DEFAULT_PAGE_SIZE, RUN_STATUS_META } from "@/lib/constants";

export const queryKeys = {
  me: ["me"] as const,
  audits: (offset: number) => ["audits", offset] as const,
  audit: (id: number) => ["audit", id] as const,
  findings: (runId: number, offset: number) => ["findings", runId, offset] as const,
  policies: (offset: number) => ["policies", offset] as const,
  policy: (id: number) => ["policy", id] as const,
  policyVersions: (id: number) => ["policy-versions", id] as const,
  documents: (offset: number, filters: string) => ["documents", offset, filters] as const,
  document: (id: number) => ["document", id] as const,
  chunks: (documentId: number) => ["chunks", documentId] as const,
};

export const useMe = (): UseQueryResult<OrgOut> =>
  useQuery({ queryKey: queryKeys.me, queryFn: () => apiFetch<OrgOut>("me") });

export const useAudits = (offset = 0): UseQueryResult<Page<AuditRunOut>> =>
  useQuery({
    queryKey: queryKeys.audits(offset),
    queryFn: () =>
      apiFetch<Page<AuditRunOut>>(`audits${pageQuery(DEFAULT_PAGE_SIZE, offset)}`),
  });

/** Polls while the run is queued/running — the 202 + poll contract. */
export const useAudit = (id: number): UseQueryResult<AuditRunOut> =>
  useQuery({
    queryKey: queryKeys.audit(id),
    queryFn: () => apiFetch<AuditRunOut>(`audits/${id}`),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (!status || RUN_STATUS_META[status].terminal) return false;
      return AUDIT_POLL_INTERVAL_MS;
    },
  });

export const useFindings = (
  runId: number,
  enabled: boolean,
  offset = 0,
): UseQueryResult<Page<FindingOut>> =>
  useQuery({
    queryKey: queryKeys.findings(runId, offset),
    queryFn: () =>
      apiFetch<Page<FindingOut>>(
        `audits/${runId}/findings${pageQuery(100, offset)}`,
      ),
    enabled,
  });

