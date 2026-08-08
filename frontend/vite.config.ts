import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  base: "/dashboard/",
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      "/dashboard/api": "http://localhost:8888",
    },
  },
});
