import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const API_TARGET = process.env.VITE_API_PROXY || "http://127.0.0.1:8000";

// Freebuff requires HMR to remain disabled; preserve server.hmr: false.
export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: Number(process.env.PORT) || 5173,
    hmr: false,
    proxy: {
      "/api": { target: API_TARGET, changeOrigin: false },
      "/health": { target: API_TARGET, changeOrigin: false },
      "/metrics": { target: API_TARGET, changeOrigin: false },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: false,
    target: "es2020",
  },
});
