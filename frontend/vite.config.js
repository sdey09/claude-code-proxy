import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  base: "/dashboard/",
  plugins: [react()],
  server: {
    proxy: {
      "/dashboard/api": "http://localhost:8888",
    },
  },
});
