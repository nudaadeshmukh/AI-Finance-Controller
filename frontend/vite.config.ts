import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Static build, no server (§3.1, §23) — reads a committed results.json per run.
export default defineConfig({
  plugins: [react()],
});
