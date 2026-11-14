import { existsSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import cesium from "vite-plugin-cesium";

const configDir = fileURLToPath(new URL(".", import.meta.url));
const cesiumBuildDir = [
  resolve(configDir, "../node_modules/cesium/Build"),
  resolve(configDir, "node_modules/cesium/Build"),
].find(existsSync);

if (!cesiumBuildDir) {
  throw new Error("Cesium build assets were not found in node_modules.");
}

export default defineConfig({
  envDir: "..",
  base: "./",
  plugins: [
    react(),
    cesium({
      cesiumBuildRootPath: cesiumBuildDir,
      cesiumBuildPath: resolve(cesiumBuildDir, "Cesium"),
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
