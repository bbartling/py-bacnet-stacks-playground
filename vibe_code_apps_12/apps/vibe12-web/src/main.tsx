import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "./App";
import { ThemeProvider } from "./contexts/theme-context";
import { AuthProvider } from "./contexts/auth-context";
import { SiteProvider } from "./contexts/site-context";
import { logger } from "./lib/logger";
/** Inline CSS in JS bundle — one fewer Lambda invocation on page load (avoids 429 on separate .css). */
import indexCss from "./index.css?inline";
import vibe12Css from "./vibe12.css?inline";

if (typeof document !== "undefined" && !document.getElementById("vibe12-inlined-styles")) {
  const el = document.createElement("style");
  el.id = "vibe12-inlined-styles";
  el.textContent = `${indexCss}\n${vibe12Css}`;
  document.head.appendChild(el);
}

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, refetchOnWindowFocus: false },
  },
});

logger.info("app", "Vibe12 Cloud boot");

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <AuthProvider>
          <BrowserRouter>
            <SiteProvider>
              <App />
            </SiteProvider>
          </BrowserRouter>
        </AuthProvider>
      </ThemeProvider>
    </QueryClientProvider>
  </StrictMode>,
);
