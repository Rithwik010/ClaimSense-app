// TanStack Query hooks over the API (one place for every query key).

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useUser } from "../lib/auth";
import { request } from "./client";
import type {
  AuditEvent,
  ClaimCheck,
  ClaimForm,
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
  PatientEob,
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

/** The most files one claim is filed from: its form's pages, 2, or up to 5 when its notes go on to
 * continuation pages (D-DOC-2, D-DOC-3). The API refuses more pages. */
export const MAX_CLAIM_FILES = 5;

/**
 * Where a claim file goes: a JSON claim to POST /v1/claims/intake, as its own text (the API keeps
 * the bytes as sent, D-DOC-1); a PDF or scan (or a file that is not valid JSON, so the API can say
 * what is wrong) to POST /v1/claims/intake/file. Both name the file in X-File-Name. A claim's form
 * pages in several files go together to POST /v1/claims/intake/files (D-DOC-2).
 */
export async function intakeRequest(file: File): Promise<{ path: string; text?: string }> {
  const isJson = file.type === "application/json" || file.name.toLowerCase().endsWith(".json");
  if (isJson) {
    const text = await file.text();
    try {
      JSON.parse(text);
      return { path: "/v1/claims/intake", text };
    } catch {
      // Not valid JSON: the file route answers with the reason.
    }
  }
  return { path: "/v1/claims/intake/file" };
}

/** A file's bytes as base64, in chunks so a large scan does not overflow the call stack. */
export async function toBase64(file: Blob): Promise<string> {
  const bytes = new Uint8Array(await file.arrayBuffer());
  let binary = "";
  for (let i = 0; i < bytes.length; i += 0x8000) {
    binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  }
  return btoa(binary);
}

/** The body of POST /v1/claims/intake/files: the files in page order, each base64-encoded. */
export async function filesBody(files: File[]): Promise<{ files: { name: string; content_base64: string }[] }> {
  return { files: await Promise.all(files.map(async (f) => ({ name: f.name, content_base64: await toBase64(f) }))) };
}

export function useUpload() {
  return useMutation({
    mutationFn: async (files: File[]) => {
      const [file] = files;
      if (!file) throw new Error("Choose a claim file first.");
      if (files.length > 1) {
        return request<IntakeResult | FiledWithErrors>("/v1/claims/intake/files", {
          method: "POST",
          json: await filesBody(files),
        });
      }
      const target = await intakeRequest(file);
      const headers = { "X-File-Name": encodeURIComponent(file.name) };
      return target.text !== undefined
        ? request<IntakeResult | FiledWithErrors>(target.path, {
            method: "POST",
            body: target.text,
            type: "application/json",
            headers,
          })
        : request<IntakeResult | FiledWithErrors>(target.path, {
            method: "POST",
            body: file,
            type: file.type || "application/octet-stream",
            headers,
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
    for (const key of [
      ["claim", claimId],
      ["audit", claimId],
      ["explanation", claimId],
      ["form", claimId],
      ["eob", claimId],
      ["overview"],
    ]) {
      void client.invalidateQueries({ queryKey: key });
    }
    client.removeQueries({ queryKey: ["check", claimId] }); // a processed claim is not checked
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

/** A claim read from our form, box by box (D-FIX-1); only asked for claims read from a form. */
export function useClaimForm(claimId: string, enabled = true) {
  return useQuery({
    queryKey: ["form", claimId],
    queryFn: () => request<ClaimForm>(`/v1/claims/${encodeURIComponent(claimId)}/form`),
    enabled: enabled && claimId !== "",
  });
}

/** What processing would find, before it runs (D-CHK-1): asked for with "Check claim", and asked
 * again after each correction while it is shown. */
export function useClaimCheck(claimId: string, enabled: boolean) {
  return useQuery({
    queryKey: ["check", claimId],
    queryFn: () => request<ClaimCheck>(`/v1/claims/${encodeURIComponent(claimId)}/check`),
    enabled: enabled && claimId !== "",
    staleTime: 0,
  });
}

/** Correct boxes of the provider's claim before processing (D-FIX-1). */
export function useCorrect(claimId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (corrections: { field: string; value: string }[]) =>
      request<ClaimForm>(`/v1/claims/${encodeURIComponent(claimId)}/corrections`, {
        method: "POST",
        json: { corrections },
      }),
    onSuccess: (form) => {
      client.setQueryData(["form", claimId], form);
      void client.invalidateQueries({ queryKey: ["check", claimId] });
      void client.invalidateQueries({ queryKey: ["claim", claimId] });
    },
  });
}

/** The patient's explanation of benefits of a decided claim (D-EOB-1). */
export function usePatientEob(claimId: string) {
  return useQuery({
    queryKey: ["eob", claimId],
    queryFn: () => request<PatientEob>(`/v1/claims/${encodeURIComponent(claimId)}/eob`),
  });
}
