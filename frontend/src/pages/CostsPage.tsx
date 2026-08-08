import StatCards from "../components/StatCards";
import CostChart from "../components/CostChart";
import ModelTable from "../components/ModelTable";
import FolderTable from "../components/FolderTable";
import { useCostsQuery } from "../queries";

export default function CostsPage() {
  const { data, error } = useCostsQuery();

  if (error) return <p className="text-sm text-err">{error.message}</p>;
  if (!data) return null;

  return (
    <>
      <h1 className="mb-2 text-2xl font-semibold">Cost &amp; Usage</h1>
      <StatCards summary={data.summary} />

      <h2 className="mt-8 text-lg text-muted">Cost over last 14 days</h2>
      <CostChart series={data.series} />

      <h2 className="mt-8 text-lg text-muted">Cost by model</h2>
      <ModelTable byModel={data.by_model} />

      <h2 className="mt-8 text-lg text-muted">Cost by folder</h2>
      <p className="text-sm text-muted">
        Grouped by the directory of each file an Edit/Write/Read tool call touched. A request that touches multiple
        folders in one turn is counted against each — folder totals can exceed the overall total.
      </p>
      <FolderTable byFolder={data.by_folder} />
    </>
  );
}
