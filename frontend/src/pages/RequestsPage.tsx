import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { getRequests } from "../api";
import FilterBar from "../components/FilterBar";
import RequestsTable from "../components/RequestsTable";
import Pagination from "../components/Pagination";
import type { RequestsResponse } from "../types";

export default function RequestsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const page = parseInt(searchParams.get("page") || "1", 10);
  const model = searchParams.get("model") || "";
  const status = searchParams.get("status") || "";

  const [data, setData] = useState<RequestsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getRequests({ page, model, status })
      .then((d) => {
        if (!cancelled) setData(d);
      })
      .catch((e) => {
        if (!cancelled) setError(e.message);
      });
    return () => {
      cancelled = true;
    };
  }, [page, model, status]);

  function updateParams(next: { model: string; status: string }) {
    const params: Record<string, string> = {};
    if (next.model) params.model = next.model;
    if (next.status) params.status = next.status;
    setSearchParams(params);
  }

  function goToPage(nextPage: number) {
    const params: Record<string, string> = { page: String(nextPage) };
    if (model) params.model = model;
    if (status) params.status = status;
    setSearchParams(params);
  }

  return (
    <>
      <h1 className="mb-2 text-2xl font-semibold">Requests</h1>
      <FilterBar models={data?.models || []} model={model} status={status} onChange={updateParams} />
      {error && <p className="text-sm text-err">{error}</p>}
      {data && (
        <>
          <p className="text-sm text-muted">
            {data.total} request{data.total !== 1 ? "s" : ""}
          </p>
          <RequestsTable rows={data.rows} />
          <Pagination page={data.page} totalPages={data.total_pages} onChange={goToPage} />
        </>
      )}
    </>
  );
}
