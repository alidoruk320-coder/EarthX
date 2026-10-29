import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import cesium from "vite-plugin-cesium";

export default defineConfig({
  envDir: "..",
  base: "./",
  plugins: [
    react(),
    cesium({
      cesiumBuildRootPath: "../node_modules/cesium/Build",
      cesiumBuildPath: "../node_modules/cesium/Build/Cesium/",
    })
  ],
  server: {
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});
