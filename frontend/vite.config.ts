import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

// Em desenvolvimento, /api vai para o FastAPI (uvicorn api.main:app --port 8000).
// host: true abre o front na rede local, para testar no celular pelo IP do computador.
// No GitHub Pages (D42) o site fica numa subpasta (/TCS-CLAUDE/): o workflow passa VITE_BASE,
// e VITE_API_URL com o endereço da API no Render. Sem elas, tudo continua na mesma origem.
export default defineConfig(({ mode }) => ({
  base: loadEnv(mode, ".", "VITE_").VITE_BASE || "/",
  plugins: [react()],
  server: { port: 5173, host: true, proxy: { "/api": "http://localhost:8000" } },
}));
