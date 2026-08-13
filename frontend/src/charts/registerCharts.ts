import {
  ArcElement,
  BarElement,
  CategoryScale,
  Chart as ChartJS,
  Legend,
  LinearScale,
  LineElement,
  PointElement,
  Tooltip,
} from "chart.js";

ChartJS.register(ArcElement, BarElement, CategoryScale, Legend, LinearScale, LineElement, PointElement, Tooltip);

export const CHART_COLORS = {
  red: "#da291c",
  redDark: "#b5120b",
  navy: "#2d3548",
  navyLight: "#6a6c6e",
  gray: "#dee2e6",
  success: "#0aa06e",
};
