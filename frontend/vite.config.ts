import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const backendTarget = "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/auth": backendTarget,
      "/chat": backendTarget,
      "/documents": backendTarget,
      "/generation": backendTarget,
      "/retrieval": backendTarget,
    },
  },
});