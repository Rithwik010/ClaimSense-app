// TanStack Query hooks over the API (one place for every query key).

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useUser } from "../lib/auth";
import { request } from "./client";
import type {
  AuditEvent,
  ClaimStatus,
  ClaimSummary,
  ClaimView,
  DecisionRecord,
  Evaluation,
  FiledWithErrors,
  Health,
  IntakeResult,
  LineOverride,
  Overview,
  Plan,
  ProviderClaimSummary,
  ProviderClaimView,
  QueueItem,
  Results,
  ReviewTier,
  SystemVersions,
} from "./types";

export function useQueue(tier: ReviewTier | null) {
  return useQuery({
    queryKey: ["queue", tier],
    queryFn: () => request<QueueItem[]>(`/v1/review/queue${tier ? `?tier=${tier}` : ""}`),
  });
}

/** A provider's own claim: their view (IN_REVIEW until final). */
export function useMyClaim(claimId: string) {
  return useQuery({
    queryKey: ["claim", claimId, "mine"],
    queryFn: () => request<ProviderClaimView>(`/v1/claims/${encodeURIComponent(claimId)}`),
  });
}

export function useHealth() {
  return useQuery({ queryKey: ["health"], queryFn: () => request<Health>("/health") });
}

export function useOverview() {
  return useQuery({ queryKey: ["overview"], queryFn: () => request<Overview>("/v1/metrics/overview") });
}

export function useSystemVersions() {
  return useQuery({ queryKey: ["system"], queryFn: () => request<SystemVersions>("/v1/metrics/system") });
}

export function useResults() {
  return useQuery({ queryKey: ["results"], queryFn: () => request<Results>("/v1/metrics/results") });
}

/** A provider's own claims (the same endpoint answers a provider with their view only). */
export function useMyClaims() {
  return useQuery({
    queryKey: ["claims", "mine"],
    queryFn: () => request<ProviderClaimSummary[]>("/v1/claims"),
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

export function useAudit(claimId: string, enabled = true) {
  return useQuery({
    queryKey: ["audit", claimId],
    queryFn: () => request<AuditEvent[]>(`/v1/claims/${encodeURIComponent(claimId)}/audit`),
    enabled: enabled && claimId !== "",
  });
}

export function useExplanation(claimId: string, enabled: boolean) {
  return useQuery({
    queryKey: ["explanation", claimId],
    queryFn: () =>
      request<string>(`/v1/claims/${encodeURIComponent(claimId)}/explanation`, {
        expect: "text",
      }),
    enabled,
  });
}

export function useEvaluation() {
  return useQuery({
    queryKey: ["evaluation"],
    queryFn: () => request<Evaluation>("/v1/metrics/evaluation"),
  });
}

/**
 * Where a claim file goes: a JSON claim as JSON to POST /v1/claims/intake; a PDF or scan (or a
 * file that is not valid JSON, so the API can say what is wrong) to POST /v1/claims/intake/file.
 */
export async function intakeRequest(file: File): Promise<{ path: string; json?: unknown }> {
  const isJson = file.type === "application/json" || file.name.toLowerCase().endsWith(".json");
  if (isJson) {
    try {
      return { path: "/v1/claims/intake", json: JSON.parse(await file.text()) as unknown };
    } catch {
      // Not valid JSON: the file route answers with the reason.
    }
  }
  return { path: "/v1/claims/intake/file" };
}

export function useUpload() {
  return useMutation({
    mutationFn: async (file: File) => {
      const target = await intakeRequest(file);
      return target.json !== undefined
        ? request<IntakeResult | FiledWithErrors>(target.path, { method: "POST", json: target.json })
        : request<IntakeResult | FiledWithErrors>(target.path, {
            method: "POST",
            body: file,
            type: file.type || "application/octet-stream",
          });
    },
  });
}

/** The plan a claim was checked against (reviewers and admins). */
export function usePlan(planId: string | null) {
  return useQuery({
    queryKey: ["plan", planId],
    queryFn: () => request<Plan>(`/v1/plans/${encodeURIComponent(planId ?? "")}`),
    enabled: planId !== null,
    staleTime: Infinity,
  });
}

function useRefresh() {
  const client = useQueryClient();
  return (claimId: string) => {
    for (const key of [["claim", claimId], ["audit", claimId], ["explanation", claimId], ["overview"]]) {
      void client.invalidateQueries({ queryKey: key });
    }
    void client.invalidateQueries({ queryKey: ["claims"] });
    void client.invalidateQueries({ queryKey: ["queue"] });
  };
}

/** A provider processes their own claim; the answer is their view (IN_REVIEW or final). */
export function useProcess() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: (claimId: string) =>
      request<ProviderClaimView>(`/v1/claims/${encodeURIComponent(claimId)}/process`, {
        method: "POST",
      }),
    onSuccess: (view) => refresh(view.claim_id),
  });
}

/** Review actions name the logged-in reviewer, whom the API checks (D-AUTH-1). */
export function useOpenReview() {
  const user = useUser();
  return useMutation({
    mutationFn: (claimId: string) =>
      request(`/v1/claims/${encodeURIComponent(claimId)}/review/open`, {
        method: "POST",
        json: { reviewer_id: user.username },
      }),
  });
}

export function useSubmitReview() {
  const user = useUser();
  const refresh = useRefresh();
  return useMutation({
    mutationFn: ({ claimId, overrides }: { claimId: string; overrides: LineOverride[] }) =>
      request<DecisionRecord>(`/v1/claims/${encodeURIComponent(claimId)}/review`, {
        method: "POST",
        json: {
          claim_id: claimId,
          reviewer_id: user.username,
          action: overrides.length ? "OVERRIDE" : "ACCEPT",
          line_overrides: overrides,
          timestamp: new Date().toISOString(),
        },
      }),
    onSuccess: (record) => refresh(record.claim_id),
  });
}
