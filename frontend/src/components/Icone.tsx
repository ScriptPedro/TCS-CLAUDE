// Ícones de traço (24×24), desenhados aqui para não depender de biblioteca
const TRACOS = {
  voltar: "M15 18l-6-6 6-6",
  seta: "M9 18l6-6-6-6",
  olho: "M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z M12 15a3 3 0 100-6 3 3 0 000 6z",
  olhoFechado: "M3 3l18 18 M10.6 5.1A10.4 10.4 0 0112 5c6.5 0 10 7 10 7a17 17 0 01-3.2 4 M6.6 6.6C3.8 8.4 2 12 2 12s3.5 7 10 7a9.7 9.7 0 005.4-1.6 M9.9 9.9a3 3 0 004.2 4.2",
  sino: "M18 8a6 6 0 10-12 0c0 7-3 9-3 9h18s-3-2-3-9 M13.7 21a2 2 0 01-3.4 0",
  ajuda: "M12 22a10 10 0 100-20 10 10 0 000 20z M9.1 9a3 3 0 015.8 1c0 2-3 3-3 3 M12 17h.01",
  pix: "M12 2.5l4.2 4.2-4.2 4.2-4.2-4.2z M12 13.1l4.2 4.2-4.2 4.2-4.2-4.2z M2.5 12l4.2-4.2 4.2 4.2-4.2 4.2z M13.1 12l4.2-4.2 4.2 4.2-4.2 4.2z",
  codigoBarras: "M3 5v14 M7 5v14 M10 5v14 M14 5v14 M17 5v14 M21 5v14",
  transferir: "M17 3l4 4-4 4 M3 7h18 M7 21l-4-4 4-4 M21 17H3",
  depositar: "M12 3v12 M7 10l5 5 5-5 M4 21h16",
  celular: "M7 2h10a2 2 0 012 2v16a2 2 0 01-2 2H7a2 2 0 01-2-2V4a2 2 0 012-2z M11 18h2",
  emprestimo: "M12 1v22 M17 5H9.5a3.5 3.5 0 000 7h5a3.5 3.5 0 010 7H6",
  casa: "M3 10.5L12 3l9 7.5V20a1 1 0 01-1 1h-5v-6H9v6H4a1 1 0 01-1-1z",
  grafico: "M3 3v18h18 M7 15l4-4 3 3 6-6",
  cartao: "M2 5h20v14H2z M2 10h20 M6 15h4",
  menu: "M4 6h16 M4 12h16 M4 18h16",
  brilho: "M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9z M19 15l.8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8z",
  mercado: "M3 4h2l2.4 11.2a1 1 0 001 .8h9.2a1 1 0 001-.8L20 8H6.2 M9 20.5a.5.5 0 100-1 .5.5 0 000 1z M18 20.5a.5.5 0 100-1 .5.5 0 000 1z",
  entrada: "M17 7L7 17 M17 17H7V7",
  saida: "M7 17L17 7 M7 7h10v10",
} as const;

export type NomeIcone = keyof typeof TRACOS;

export default function Icone({ nome, tamanho = 24 }: { nome: NomeIcone; tamanho?: number }) {
  return (
    <svg width={tamanho} height={tamanho} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}
      strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d={TRACOS[nome]} />
    </svg>
  );
}
