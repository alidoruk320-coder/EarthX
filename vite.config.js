import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import cesium from "vite-plugin-cesium";

export default defineConfig({
  base: "./",
  plugins: [
    react(),
    cesium()
  ]
});
