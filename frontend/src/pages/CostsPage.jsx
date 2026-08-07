import { useEffect, useState } from "react";
import { getCosts } from "../api.js";
import StatCards from "../components/StatCards.jsx";
import CostChart from "../components/CostChart.jsx";
import ModelTable from "../components/ModelTable.jsx";
import FolderTable from "../components/FolderTable.jsx";

export default function CostsPage() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    getCosts()
      .then((d) => {
        if (!cancelled) setData(d);
      })
      .catch((e) => {
        if (!cancelled) setError(e.message);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (error) return <p className="meta err">{error}</p>;
  if (!data) return null;

  return (
    <>
      <h1>Cost &amp; Usage</h1>
      <StatCards summary={data.summary} />

      <h2>Cost over last 14 days</h2>
      <CostChart series={data.series} />

      <h2>Cost by model</h2>
      <ModelTable byModel={data.by_model} />

      <h2>Cost by folder</h2>
      <p className="meta">
        Grouped by the directory of each file an Edit/Write/Read tool call touched. A request that touches multiple
        folders in one turn is counted against each — folder totals can exceed the overall total.
      </p>
      <FolderTable byFolder={data.by_folder} />
    </>
  );
}
