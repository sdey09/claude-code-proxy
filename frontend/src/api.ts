import type { CostsResponse, RequestDetailResponse, RequestsResponse } from "./types";

async function getJSON<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.error || `Request failed: ${res.status}`);
  }
  return res.json();
}

export interface GetRequestsParams {
  page?: number;
  model?: string;
  status?: string;
}

export function getRequests({ page = 1, model = "", status = "" }: GetRequestsParams = {}): Promise<RequestsResponse> {
  const params = new URLSearchParams();
  if (page) params.set("page", String(page));
  if (model) params.set("model", model);
  if (status) params.set("status", status);
  return getJSON(`/dashboard/api/requests?${params.toString()}`);
}

export function getRequest(id: string): Promise<RequestDetailResponse> {
  return getJSON(`/dashboard/api/requests/${id}`);
}

export function getCosts(): Promise<CostsResponse> {
  return getJSON("/dashboard/api/costs");
}
