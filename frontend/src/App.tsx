import { Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "./auth/AuthContext";
import { RequireAuth } from "./auth/RequireAuth";
import { AppLayout } from "./components/layout/AppLayout";
import { LoginPage } from "./pages/LoginPage";
import { DashboardsHomePage } from "./pages/DashboardsHomePage";
import { SobretiempoDashboardPage } from "./pages/SobretiempoDashboardPage";
import { CapacitacionDashboardPage } from "./pages/CapacitacionDashboardPage";

// El dashboard tambien se usa standalone en el HTML exportado (sin
// AuthProvider), asi que no puede llamar useAuth() el mismo — este wrapper
// hace ese trabajo solo cuando corre dentro de la app real, y le pasa el rol
// como prop.
function SobretiempoDashboardRoute() {
  const { user } = useAuth();
  return <SobretiempoDashboardPage userRole={user?.role} />;
}

function CapacitacionDashboardRoute() {
  const { user } = useAuth();
  return <CapacitacionDashboardPage userRole={user?.role} />;
}

export function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          element={
            <RequireAuth>
              <AppLayout />
            </RequireAuth>
          }
        >
          <Route path="/dashboards" element={<DashboardsHomePage />} />
          <Route path="/dashboards/sobretiempo" element={<SobretiempoDashboardRoute />} />
          <Route path="/dashboards/capacitacion" element={<CapacitacionDashboardRoute />} />
        </Route>
        <Route path="/" element={<Navigate to="/dashboards" replace />} />
        <Route path="*" element={<Navigate to="/dashboards" replace />} />
      </Routes>
    </AuthProvider>
  );
}
