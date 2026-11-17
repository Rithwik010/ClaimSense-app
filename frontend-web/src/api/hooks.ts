// TanStack Query hooks over the API (one place for every query key).

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useUser } from "../lib/auth";
import { request } from "./client";
import type {
  AuditEvent,
  AuditSearch,
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
  MemberBenefits,
  MemberClaim,
  MemberProfile,
  Notifications,
  OtherReviewer,
  Overview,
  PatientEob,
  Plan,
  PlanSummary,
  PolicyDetail,
  PolicySummary,
  ProviderClaimSummary,
  ProviderClaimView,
  QueueItem,
  Results,
  ReviewQuality,
  ReviewTier,
  Role,
  SystemVersions,
  UserInfo,
} from "./types";

/** Lists and counts ask the API again on their own while their page is open (fix 9): new claims
 * and decisions show without a reload. A page in a background tab does not ask. */
export const REFRESH_MS = 30_000;

export function useQueue(tier: ReviewTier | null) {
  return useQuery({
    queryKey: ["queue", tier],
    queryFn: () => request<QueueItem[]>(`/v1/review/queue${tier ? `?tier=${tier}` : ""}`),
    refetchInterval: REFRESH_MS,
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
  return useQuery({
    queryKey: ["overview"],
    queryFn: () => request<Overview>("/v1/metrics/overview"),
    refetchInterval: REFRESH_MS,
  });
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
    refetchInterval: REFRESH_MS,
  });
}

export function useClaims(statuses: ClaimStatus[] = []) {
  const query = statuses.map((s) => `status=${s}`).join("&");
  return useQuery({
    queryKey: ["claims", statuses],
    queryFn: () => request<ClaimSummary[]>(`/v1/claims${query ? `?${query}` : ""}`),
    refetchInterval: REFRESH_MS,
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

/** Review actions name the logged-in reviewer, whom the API checks (D-AUTH-1). The answer names
 * any other reviewer who opened the claim in the last 30 minutes (D-REV-10). */
export function useOpenReview() {
  const user = useUser();
  const client = useQueryClient();
  return useMutation({
    mutationFn: (claimId: string) =>
      request<{ claim_id: string; opened: string; others: OtherReviewer[] }>(
        `/v1/claims/${encodeURIComponent(claimId)}/review/open`,
        { method: "POST", json: { reviewer_id: user.username } },
      ),
    onSuccess: (opened) => client.setQueryData(["others", opened.claim_id], opened.others),
  });
}

/** Other reviewers with the claim open (D-REV-10), asked again every minute while it is shown. */
export function useOthersReviewing(claimId: string, enabled: boolean) {
  return useQuery({
    queryKey: ["others", claimId],
    queryFn: () => request<OtherReviewer[]>(`/v1/claims/${encodeURIComponent(claimId)}/review/others`),
    enabled: enabled && claimId !== "",
    refetchInterval: 60_000,
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

// --- A member's own pages (D-MEM-1): only the /v1/member routes, which answer members only ------

/** The member's claims (those in which they are the patient). */
export function useMemberClaims() {
  return useQuery({
    queryKey: ["member", "claims"],
    queryFn: () => request<MemberClaim[]>("/v1/member/claims"),
    refetchInterval: REFRESH_MS,
  });
}

export function useMemberClaim(claimId: string) {
  return useQuery({
    queryKey: ["member", "claim", claimId],
    queryFn: () => request<MemberClaim>(`/v1/member/claims/${encodeURIComponent(claimId)}`),
  });
}

/** The patient EOB of the member's decided claim: the one its provider gets (D-EOB-1). */
export function useMemberEob(claimId: string, enabled: boolean) {
  return useQuery({
    queryKey: ["member", "eob", claimId],
    queryFn: () => request<PatientEob>(`/v1/member/claims/${encodeURIComponent(claimId)}/eob`),
    enabled,
  });
}

export function useMemberBenefits() {
  return useQuery({ queryKey: ["member", "benefits"], queryFn: () => request<MemberBenefits>("/v1/member/benefits") });
}

export function useMemberProfile() {
  return useQuery({ queryKey: ["member", "profile"], queryFn: () => request<MemberProfile>("/v1/member/profile") });
}

// --- Follow-ups, appeals and feedback (D-FUP-1, D-APL-1, D-FBK-1) --------------------------------

function claimPost<T>(claimId: string, action: string, json?: unknown) {
  return request<T>(`/v1/claims/${encodeURIComponent(claimId)}/${action}`, { method: "POST", json });
}

/** A provider's follow-up on their decided claim; the answer is their view of it. */
export function useFollowUp(claimId: string) {
  const refresh = useRefresh();
  const client = useQueryClient();
  return useMutation({
    mutationFn: (
      step: { kind: "reopen" } | { kind: "documentation"; text: string } | { kind: "appeal"; reason: string },
    ) =>
      step.kind === "reopen"
        ? claimPost<ProviderClaimView>(claimId, "reopen")
        : step.kind === "documentation"
          ? claimPost<ProviderClaimView>(claimId, "documentation", { text: step.text })
          : claimPost<ProviderClaimView>(claimId, "appeal", { reason: step.reason }),
    onSuccess: (view) => {
      client.setQueryData(["claim", claimId, "mine"], view);
      refresh(claimId);
    },
  });
}

/** A member appeals their denied claim; the answer is their view of it. */
export function useMemberAppeal(claimId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (reason: string) =>
      request<MemberClaim>(`/v1/member/claims/${encodeURIComponent(claimId)}/appeal`, {
        method: "POST",
        json: { reason },
      }),
    onSuccess: (claim) => {
      client.setQueryData(["member", "claim", claimId], claim);
      void client.invalidateQueries({ queryKey: ["member", "claims"] });
    },
  });
}

export interface CriterionFix {
  criterion_id: string;
  status: "MET" | "NOT_MET" | "NOT_DOCUMENTED" | "NOT_APPLICABLE";
  quote?: string | null;
}

/** The finalizing reviewer's corrections of the model's criteria (D-FBK-1). */
export function useFeedback(claimId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (lines: { line_no: number; criteria: CriterionFix[] }[]) =>
      claimPost<{ claim_id: string; criteria_corrected: number }>(claimId, "feedback", { lines }),
    onSuccess: () => void client.invalidateQueries({ queryKey: ["audit", claimId] }),
  });
}

// --- Everyone (D-NTF-1, D-POL-9, D-AUTH-2) ---------------------------------------------------------

export function useNotifications() {
  return useQuery({
    queryKey: ["notifications"],
    queryFn: () => request<Notifications>("/v1/notifications"),
    refetchInterval: REFRESH_MS,
  });
}

export function usePolicies() {
  return useQuery({
    queryKey: ["policies"],
    queryFn: () => request<PolicySummary[]>("/v1/policies"),
    staleTime: Infinity,
  });
}

export function usePolicy(policyId: string | null) {
  return useQuery({
    queryKey: ["policy", policyId],
    queryFn: () => request<PolicyDetail>(`/v1/policies/${encodeURIComponent(policyId ?? "")}`),
    enabled: policyId !== null,
    staleTime: Infinity,
  });
}

export function useChangePassword() {
  return useMutation({
    mutationFn: (body: { current_password: string; new_password: string }) =>
      request<void>("/v1/auth/password", { method: "POST", json: body }),
  });
}

// --- The admin's (D-AUTH-2, D-AUD-1, D-QLT-1) -------------------------------------------------------

export function useUsers() {
  return useQuery({ queryKey: ["users"], queryFn: () => request<UserInfo[]>("/v1/users") });
}

export interface NewUser {
  username: string;
  display_name: string;
  role: Role;
  password: string;
  provider_id?: string | null;
  member_id?: string | null;
}

export function useUserAdmin() {
  const client = useQueryClient();
  const done = () => void client.invalidateQueries({ queryKey: ["users"] });
  const path = (username: string, action: string) => `/v1/users/${encodeURIComponent(username)}/${action}`;
  return {
    create: useMutation({
      mutationFn: (body: NewUser) => request<UserInfo>("/v1/users", { method: "POST", json: body }),
      onSuccess: done,
    }),
    password: useMutation({
      mutationFn: ({ username, password }: { username: string; password: string }) =>
        request<void>(path(username, "password"), { method: "POST", json: { password } }),
      onSuccess: done,
    }),
    active: useMutation({
      mutationFn: ({ username, active }: { username: string; active: boolean }) =>
        request<void>(path(username, "active"), { method: "POST", json: { active } }),
      onSuccess: done,
    }),
    unlock: useMutation({
      mutationFn: (username: string) => request<void>(path(username, "unlock"), { method: "POST" }),
      onSuccess: done,
    }),
  };
}

export interface AuditQuery {
  claim_id?: string;
  actor?: string;
  event_type?: string;
  since?: string;
  until?: string;
}

/** The admin's audit search; `query` null: nothing searched yet. */
export function useAuditSearch(query: AuditQuery | null) {
  const params = new URLSearchParams(
    Object.entries(query ?? {}).filter((entry): entry is [string, string] => Boolean(entry[1])),
  );
  return useQuery({
    queryKey: ["audit-search", params.toString()],
    queryFn: () => request<AuditSearch>(`/v1/audit/events?${params.toString()}`),
    enabled: query !== null,
  });
}

export function useQuality() {
  return useQuery({
    queryKey: ["quality"],
    queryFn: () => request<ReviewQuality>("/v1/metrics/quality"),
    refetchInterval: REFRESH_MS,
  });
}

// --- The member's plan summary (P3.2) ----------------------------------------------------------------

export function usePlanSummary() {
  return useQuery({
    queryKey: ["member", "plan-summary"],
    queryFn: () => request<PlanSummary>("/v1/member/plan-summary"),
    staleTime: Infinity,
  });
}
