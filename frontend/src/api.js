async function getJSON(url) {
  const res = await fetch(url);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.error || `Request failed: ${res.status}`);
  }
  return res.json();
}

export function getRequests({ page = 1, model = "", status = "" } = {}) {
  const params = new URLSearchParams();
  if (page) params.set("page", page);
  if (model) params.set("model", model);
  if (status) params.set("status", status);
  return getJSON(`/dashboard/api/requests?${params.toString()}`);
}

export function getRequest(id) {
  return getJSON(`/dashboard/api/requests/${id}`);
}

export function getCosts() {
  return getJSON("/dashboard/api/costs");
}
