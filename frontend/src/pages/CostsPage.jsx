import { useEffect, useState } from "react";
import { getCosts } from "../api.js";
import StatCards from "../components/StatCards.jsx";
import CostChart from "../components/CostChart.jsx";
import ModelTable from "../components/ModelTable.jsx";

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
    </>
  );
}
