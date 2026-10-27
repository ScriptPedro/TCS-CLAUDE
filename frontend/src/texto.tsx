import { Fragment, type ReactNode } from "react";

/** Converte "**negrito**" (formato dos textos do back-end) em <strong>. */
export function Rico({ texto }: { texto: string }): ReactNode {
  const partes = texto.split(/(\*\*[^*]+\*\*)/g);
  return partes.map((p, i) =>
    p.startsWith("**") && p.endsWith("**") ? <strong key={i}>{p.slice(2, -2)}</strong> : <Fragment key={i}>{p}</Fragment>,
  );
}

/** Markdown simples do texto completo: títulos (#), listas (- ou 1.) e parágrafos. */
export function Markdown({ texto }: { texto: string }) {
  const blocos: ReactNode[] = [];
  let lista: string[] = [];
  const fecharLista = () => {
    if (lista.length) {
      blocos.push(<ul key={blocos.length}>{lista.map((l, i) => <li key={i}><Rico texto={l} /></li>)}</ul>);
      lista = [];
    }
  };
  for (const linha of texto.split("\n").map((l) => l.trim())) {
    const item = linha.match(/^(?:[-*]|\d+\.)\s+(.*)$/);
    if (item) {
      lista.push(item[1]);
      continue;
    }
    fecharLista();
    if (!linha) continue;
    const titulo = linha.match(/^#+\s+(.*)$/);
    blocos.push(titulo ? <h4 key={blocos.length}><Rico texto={titulo[1]} /></h4> : <p key={blocos.length}><Rico texto={linha} /></p>);
  }
  fecharLista();
  return <div className="markdown">{blocos}</div>;
}

export const pct = (x: number) => `${Math.round(x * 100)}%`;
export const capitalizar = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);
