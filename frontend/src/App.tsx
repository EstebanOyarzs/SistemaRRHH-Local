import { Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./auth/AuthContext";
import { RequireAuth } from "./auth/RequireAuth";
import { AppLayout } from "./components/layout/AppLayout";
import { LoginPage } from "./pages/LoginPage";
import { DashboardsHomePage } from "./pages/DashboardsHomePage";
import { SobretiempoDashboardPage } from "./pages/SobretiempoDashboardPage";

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
          <Route path="/dashboards/sobretiempo" element={<SobretiempoDashboardPage />} />
        </Route>
        <Route path="/" element={<Navigate to="/dashboards" replace />} />
        <Route path="*" element={<Navigate to="/dashboards" replace />} />
      </Routes>
    </AuthProvider>
  );
}
