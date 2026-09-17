import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  base: "./",
  clearScreen: false,
  server: { port: 5232, strictPort: true },
  build: { outDir: "dist", emptyOutDir: true },
});
