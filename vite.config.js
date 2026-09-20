import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import cesium from "vite-plugin-cesium";

export default defineConfig({
  base: "/EarthX/",          // ← bu satır çok önemli
  plugins: [
    react(),
    cesium()
  ]
});