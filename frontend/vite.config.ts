import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Em desenvolvimento, /api vai para o FastAPI (uvicorn api.main:app --port 8000).
// host: true abre o front na rede local, para testar no celular pelo IP do computador.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, host: true, proxy: { "/api": "http://localhost:8000" } },
});
