import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// ScoreWise admin panel — a standalone SPA (not part of the web/ Next.js
// app) that talks to the FastAPI backend directly from the browser. See
// src/api.ts for why: it reuses the existing /api/v1/auth/login endpoint
// with no server-side proxy of its own.
export default defineConfig({
  plugins: [react()],
});
