// TanStack Query hooks over the API (one place for every query key).

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useSession } from "../lib/session";
import { request } from "./client";
import type {
  AuditEvent,
  ClaimStatus,
  ClaimSummary,
  ClaimView,
  DecisionRecord,
  Evaluation,
  FiledWithErrors,
  IntakeResult,
  LineOverride,
  QueueItem,
  ReviewTier,
} from "./types";

export function useQueue(tier: ReviewTier | null) {
  const { role } = useSession();
  return useQuery({
    queryKey: ["queue", tier, role],
    queryFn: () =>
      request<QueueItem[]>(`/v1/review/queue${tier ? `?tier=${tier}` : ""}`, { role }),
    enabled: role !== "provider",
  });
}

export function useClaims(statuses: ClaimStatus[] = []) {
  const query = statuses.map((s) => `status=${s}`).join("&");
  return useQuery({
    queryKey: ["claims", statuses],
    queryFn: () => request<ClaimSummary[]>(`/v1/claims${query ? `?${query}` : ""}`),
  });
}

export function useClaim(claimId: string) {
  return useQuery({
    queryKey: ["claim", claimId],
    queryFn: () => request<ClaimView>(`/v1/claims/${encodeURIComponent(claimId)}`),
  });
}

export function useAudit(claimId: string) {
  return useQuery({
    queryKey: ["audit", claimId],
    queryFn: () => request<AuditEvent[]>(`/v1/claims/${encodeURIComponent(claimId)}/audit`),
  });
}

export function useExplanation(claimId: string, enabled: boolean) {
  return useQuery({
    queryKey: ["explanation", claimId],
    queryFn: () => request<string>(`/v1/claims/${encodeURIComponent(claimId)}/explanation`),
    enabled,
  });
}

export function useEvaluation() {
  return useQuery({
    queryKey: ["evaluation"],
    queryFn: () => request<Evaluation>("/v1/metrics/evaluation"),
  });
}

export function useUpload() {
  return useMutation({
    mutationFn: (file: File) =>
      request<IntakeResult | FiledWithErrors>("/v1/claims/intake/file", {
        method: "POST",
        body: file,
        type: file.type || "application/octet-stream",
      }),
  });
}

function useRefresh() {
  const client = useQueryClient();
  return (claimId: string) => {
    for (const key of [["claim", claimId], ["audit", claimId], ["explanation", claimId]]) {
      void client.invalidateQueries({ queryKey: key });
    }
    void client.invalidateQueries({ queryKey: ["claims"] });
    void client.invalidateQueries({ queryKey: ["queue"] });
  };
}

export function useProcess() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: (claimId: string) =>
      request<DecisionRecord>(`/v1/claims/${encodeURIComponent(claimId)}/process`, {
        method: "POST",
      }),
    onSuccess: (record) => refresh(record.claim_id),
  });
}

export function useOpenReview() {
  const { role } = useSession();
  return useMutation({
    mutationFn: ({ claimId, reviewerId }: { claimId: string; reviewerId: string }) =>
      request(`/v1/claims/${encodeURIComponent(claimId)}/review/open`, {
        method: "POST",
        role,
        json: { reviewer_id: reviewerId },
      }),
  });
}

export function useSubmitReview() {
  const { role, reviewerId } = useSession();
  const refresh = useRefresh();
  return useMutation({
    mutationFn: ({ claimId, overrides }: { claimId: string; overrides: LineOverride[] }) =>
      request<DecisionRecord>(`/v1/claims/${encodeURIComponent(claimId)}/review`, {
        method: "POST",
        role,
        json: {
          claim_id: claimId,
          reviewer_id: reviewerId,
          action: overrides.length ? "OVERRIDE" : "ACCEPT",
          line_overrides: overrides,
          timestamp: new Date().toISOString(),
        },
      }),
    onSuccess: (record) => refresh(record.claim_id),
  });
}
