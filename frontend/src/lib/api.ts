export type SellerProfile = { offering: string; ideal_customer: string };
export type ResearchInput = { company_name: string; target_url: string; pasted_text: string; link_confirmed: boolean };
export type RunStatus = "queued" | "running" | "needs_input" | "needs_confirmation" | "completed" | "failed";
export type Stage = "parsing" | "collecting" | "analyzing" | "matching" | "writing" | "verifying";
export type Progress = { stage: Stage; status: "active" | "complete" | "failed"; revision_attempt: number };
export type Source = { id: string; type: "scraped" | "search" | "user_provided"; title: string; url: string | null; excerpt: string; retrieved_at: string };
export type Claim = { id: string; section: "snapshot" | "trigger" | "need" | "role"; text: string; source_ids: string[]; verification_status: "verified" };
export type EmailSegment = { id: string; text: string; source_ids: string[] };
export type EmailEdit = { subject: string; body: string };
export type FinalBrief = { company_name: string; claims: Claim[]; email: { subject: EmailSegment; paragraphs: EmailSegment[] }; sources: Source[]; limited_data: boolean; evidence_limitations: string[]; verification: { checked_units: number; supported_units: number; removed_units: number; revision_attempts: number } };
export type BriefDetail = { id: string; request: ResearchInput; status: RunStatus; progress: Progress[]; result: FinalBrief | null; email_edit: EmailEdit | null; version: number; error_code: string | null; message: string | null; created_at: string; updated_at: string };
export type BriefSummary = { id: string; company_name: string; status: RunStatus; limited_data: boolean; created_at: string };
export type BriefPage = { items: BriefSummary[]; next_offset: number | null };
export type AcceptedRun = { id: string; status: RunStatus; version: number };

export const statusLabels: Record<RunStatus, string> = { queued: "Queued", running: "In progress", needs_input: "Check input", needs_confirmation: "Confirm link", completed: "Ready", failed: "Interrupted" };
export const isActive = (status: RunStatus) => status === "queued" || status === "running";

export class ApiError extends Error {
  constructor(message: string, public status = 0, public fields: Record<string, string> = {}) { super(message); }
}

export function apiUrl(path: string) {
  const base = process.env.NEXT_PUBLIC_API_BASE_URL?.trim().replace(/\/$/, "");
  if (!base) throw new ApiError("The workspace is not connected yet. Please try again once setup is complete.");
  try {
    const url = new URL(base);
    if (!["http:", "https:"].includes(url.protocol) || url.pathname !== "/" || url.search || url.hash || url.username || url.password) throw new Error();
  } catch {
    throw new ApiError("The workspace connection is not configured correctly. Please check the backend address in setup.");
  }
  return `${base}/api${path}`;
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const timeout = AbortSignal.timeout(15000);
  const signal = init.signal ? AbortSignal.any([init.signal, timeout]) : timeout;
  let response: Response;
  try {
    response = await fetch(apiUrl(path), { ...init, signal, cache: "no-store", headers: { ...(init.body ? { "Content-Type": "application/json" } : {}), ...init.headers } });
  } catch (error) {
    if (init.signal?.aborted) throw error;
    if (error instanceof ApiError) throw error;
    throw new ApiError("We couldn’t reach the workspace. Check your connection and try again. Your input is still here.");
  }
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    const fields: Record<string, string> = {};
    if (Array.isArray(data.details)) for (const detail of data.details) {
      const name = detail.loc?.[1];
      if (typeof name === "string" && typeof detail.msg === "string") fields[name] = detail.msg.replace(/^Value error, /, "");
    }
    throw new ApiError(data.message || (response.status === 422 ? "Check the highlighted fields and try again." : "This action could not be completed. Please try again."), response.status, fields);
  }
  if (response.status === 204) return undefined as T;
  return response.json();
}

export function safeSourceUrl(value: string | null): string | null {
  if (!value) return null;
  try { const url = new URL(value); return ["http:", "https:"].includes(url.protocol) && !url.username && !url.password ? url.href : null; } catch { return null; }
}
export function sourceDomain(value: string) { return new URL(value).hostname.replace(/^www\./, ""); }
export function messageOf(error: unknown) { return error instanceof Error ? error.message : "Something went wrong. Please try again."; }
