import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The backend's CORS allows exactly this origin (http://localhost:5173), so keep the port fixed.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, strictPort: true },
});
