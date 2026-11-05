import type { Classe } from "../types";

type Parte = Pick<Classe, "classe" | "nome" | "pct" | "por_mil"> & { cor?: string };

/** Cor da cédula do Real associada à classe (tokens --nota-* em styles.css); a cor da API é o fallback. */
export const corDa = (p: { classe: string; cor?: string }) => `var(--nota-${p.classe}${p.cor ? `, ${p.cor}` : ""})`;

interface Props {
  partes: Parte[];
  titulo?: string;
  animar?: boolean;
}

// Ordem fixa, do menor para o maior risco: cada cor fica sempre no mesmo lugar da barra
const ORDEM = ["liquidez", "renda_fixa", "multimercado", "acoes", "previdencia"];
const posicao = (classe: string) => {
  const i = ORDEM.indexOf(classe);
  return i < 0 ? ORDEM.length : i;
};

/** Barra "de cada R$ 1.000": uma faixa por classe, larguras proporcionais, legenda com o valor em reais. */
export default function Notas({ partes, titulo, animar = false }: Props) {
  const visiveis = partes.filter((p) => p.pct > 0).sort((a, b) => posicao(a.classe) - posicao(b.classe));
  return (
    <figure className="notas">
      <div className={animar ? "notas-barra animar" : "notas-barra"} aria-hidden>
        {visiveis.map((p) => <span key={p.classe} style={{ flex: `${p.pct} 1 0`, background: corDa(p) }} />)}
      </div>
      <figcaption>
        {titulo && <p className="notas-titulo">{titulo}</p>}
        <ul className="notas-legenda">
          {visiveis.map((p) => (
            <li key={p.classe}>
              <span className="amostra" style={{ background: corDa(p) }} aria-hidden />
              <span className="notas-nome">{p.nome}</span>
              <span className="notas-valor">R$ {p.por_mil}</span>
              <span className="notas-pct">{p.pct}%</span>
            </li>
          ))}
        </ul>
      </figcaption>
    </figure>
  );
}
