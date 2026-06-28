import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { applyTheme, loadStoredTheme } from "./theme/theme";
import { ThemeProvider } from "./theme/ThemeContext";
import { TimezoneProvider } from "./theme/TimezoneContext";
import "./index.css";

applyTheme(loadStoredTheme());

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ThemeProvider>
      <TimezoneProvider>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </TimezoneProvider>
    </ThemeProvider>
  </StrictMode>,
);
