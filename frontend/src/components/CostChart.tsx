import {
  BarController,
  BarElement,
  CategoryScale,
  Chart as ChartJS,
  LinearScale,
  LineController,
  LineElement,
  PointElement,
  Legend,
  Tooltip,
} from "chart.js";
import { Chart } from "react-chartjs-2";
import type { CostSeries } from "../types";

ChartJS.register(
  BarController,
  LineController,
  BarElement,
  LineElement,
  PointElement,
  CategoryScale,
  LinearScale,
  Legend,
  Tooltip
);

interface CostChartProps {
  series: CostSeries;
}

export default function CostChart({ series }: CostChartProps) {
  const data = {
    labels: series.labels,
    datasets: [
      {
        type: "bar" as const,
        label: "Cost (USD)",
        data: series.cost,
        backgroundColor: "#7c9cff",
        yAxisID: "y",
      },
      {
        type: "line" as const,
        label: "Requests",
        data: series.count,
        borderColor: "#f2a154",
        backgroundColor: "#f2a154",
        yAxisID: "y1",
        tension: 0.3,
      },
    ],
  };

  const options = {
    responsive: true,
    scales: {
      y: { beginAtZero: true, position: "left" as const, title: { display: true, text: "USD" } },
      y1: {
        beginAtZero: true,
        position: "right" as const,
        grid: { drawOnChartArea: false },
        title: { display: true, text: "Requests" },
      },
    },
  };

  return <Chart type="bar" data={data} options={options} height={90} />;
}
