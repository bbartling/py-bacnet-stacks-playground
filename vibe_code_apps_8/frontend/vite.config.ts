import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "path";

/** Production: nginx serves under /app8/ (Docker BAS Lite + Caddy). */
const rawBase = (process.env.VITE_BASE_PATH ?? "/app8").trim();
const base = rawBase ? (rawBase.startsWith("/") ? rawBase : `/${rawBase}`).replace(/\/?$/, "/") : "/";

const devProxyTarget = (process.env.VITE_DEV_PROXY_TARGET ?? "").trim();

export default defineConfig({
  base,
  plugins: [react(), tailwindcss()],
  resolve: { alias: { "@": path.resolve(__dirname, "./src") } },
  build: {
    outDir: "dist",
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
