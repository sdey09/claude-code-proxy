import FilterBar from "../components/FilterBar";
import RequestsTable from "../components/RequestsTable";
import Pagination from "../components/Pagination";
import { useRequestsQuery } from "../queries";
import { useFiltersStore } from "../store/filtersStore";

export default function RequestsPage() {
  const { page, model, status, setFilters, setPage } = useFiltersStore();
  const { data, error } = useRequestsQuery({ page, model, status });

  return (
    <>
      <h1 className="mb-2 text-2xl font-semibold">Requests</h1>
      <FilterBar models={data?.models || []} model={model} status={status} onChange={setFilters} />
      {error && <p className="text-sm text-err">{error.message}</p>}
      {data && (
        <>
          <p className="text-sm text-muted">
            {data.total} request{data.total !== 1 ? "s" : ""}
          </p>
          <RequestsTable rows={data.rows} />
          <Pagination page={data.page} totalPages={data.total_pages} onChange={setPage} />
        </>
      )}
    </>
  );
}
