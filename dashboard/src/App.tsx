import { NavLink, Route, Routes } from "react-router-dom";
import { SwarmMonBrand } from "./components/SwarmMonBrand";
import { SettingsGearLink } from "./components/SettingsGearLink";
import FleetPage from "./pages/FleetPage";
import IncidentsPage from "./pages/IncidentsPage";
import ReportPage from "./pages/ReportPage";
import SettingsPage from "./pages/SettingsPage";

const NAV = [
  { to: "/", label: "Fleet", end: true },
  { to: "/incidents", label: "Incidents" },
  { to: "/report", label: "Report" },
] as const;

export default function App() {
  return (
    <div className="app-shell">
      <header className="app-header">
        <SwarmMonBrand />
        <div className="app-header-actions">
          <nav className="app-nav" aria-label="Main">
            {NAV.map(({ to, label, ...rest }) => (
              <NavLink
                key={to}
                to={to}
                end={"end" in rest ? rest.end : undefined}
                className={({ isActive }) =>
                  `app-nav-link${isActive ? " app-nav-link-active" : ""}`
                }
              >
                {label}
              </NavLink>
            ))}
          </nav>
          <SettingsGearLink />
        </div>
      </header>
      <main className="app-main">
        <Routes>
          <Route path="/" element={<FleetPage />} />
          <Route path="/incidents" element={<IncidentsPage />} />
          <Route path="/report" element={<ReportPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Routes>
      </main>
    </div>
  );
}
