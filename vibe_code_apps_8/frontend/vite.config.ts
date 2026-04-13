import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "path";

/** Production: served by VOLTTRON agent at http://host:8080/app8/ */
const rawBase = (process.env.VITE_BASE_PATH ?? "/app8").trim();
const base = rawBase ? (rawBase.startsWith("/") ? rawBase : `/${rawBase}`).replace(/\/?$/, "/") : "/";

const devProxyTarget = (process.env.VITE_DEV_PROXY_TARGET ?? "").trim();

export default defineConfig({
  base,
  plugins: [react(), tailwindcss()],
  resolve: { alias: { "@": path.resolve(__dirname, "./src") } },
  build: {
    outDir: "../volttron_data/ben_bacnet/app8_web_agent/app8_web_agent/webroot",
    emptyOutDir: true,
  },
  server: {
    host: "0.0.0.0",
    allowedHosts: ["localhost", ".local"],
    proxy: devProxyTarget
      ? {
          "^/app8/api": {
            target: devProxyTarget,
            changeOrigin: true,
          },
        }
      : {},
  },
});
