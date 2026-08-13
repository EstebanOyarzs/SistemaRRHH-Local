import { Link } from "react-router-dom";
import "./DashboardsHomePage.css";

const DASHBOARDS = [
  {
    slug: "sobretiempo",
    name: "Sobretiempo",
    description: "Control mensual de horas extra vs. presupuesto por gerencia.",
  },
];

export function DashboardsHomePage() {
  return (
    <div>
      <h1>Dashboards</h1>
      <p className="dashboards-home__intro">Selecciona un dashboard para ver el detalle.</p>
      <div className="dashboards-home__grid">
        {DASHBOARDS.map((d) => (
          <Link key={d.slug} to={`/dashboards/${d.slug}`} className="card dashboards-home__card">
            <h3>{d.name}</h3>
            <p>{d.description}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}
