/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Endereço da API quando o front é publicado em outro domínio (GitHub Pages → Render, D42). */
  readonly VITE_API_URL?: string;
  /** Subpasta em que o site é publicado (ex.: "/TCS-CLAUDE/"); o padrão é "/". */
  readonly VITE_BASE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
