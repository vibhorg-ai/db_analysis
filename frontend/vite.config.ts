import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": "http://127.0.0.1:8004",
      "/ws": { target: "ws://127.0.0.1:8004", ws: true },
      "/health": "http://127.0.0.1:8004",
      "/metrics": "http://127.0.0.1:8004",
    },
  },
});
