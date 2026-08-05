import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { getRequests } from "../api.js";
import FilterBar from "../components/FilterBar.jsx";
import RequestsTable from "../components/RequestsTable.jsx";
import Pagination from "../components/Pagination.jsx";

export default function RequestsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const page = parseInt(searchParams.get("page") || "1", 10);
  const model = searchParams.get("model") || "";
  const status = searchParams.get("status") || "";

  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

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

  function updateParams(next) {
    const params = {};
    if (next.model) params.model = next.model;
    if (next.status) params.status = next.status;
    setSearchParams(params);
  }

  function goToPage(nextPage) {
    const params = { page: String(nextPage) };
    if (model) params.model = model;
    if (status) params.status = status;
    setSearchParams(params);
  }

  return (
    <>
      <h1>Requests</h1>
      <FilterBar models={data?.models || []} model={model} status={status} onChange={updateParams} />
      {error && <p className="meta err">{error}</p>}
      {data && (
        <>
          <p className="meta">
            {data.total} request{data.total !== 1 ? "s" : ""}
          </p>
          <RequestsTable rows={data.rows} />
          <Pagination page={data.page} totalPages={data.total_pages} onChange={goToPage} />
        </>
      )}
    </>
  );
}
