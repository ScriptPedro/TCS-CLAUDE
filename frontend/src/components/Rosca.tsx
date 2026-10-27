import { useState } from "react";
import type { Classe } from "../types";

/** Gráfico de rosca em SVG puro: uma fatia por classe com % > 0, centro mostra a fatia em foco. */
export default function Rosca({ classes }: { classes: Classe[] }) {
  const fatias = classes.filter((c) => c.pct > 0);
  const [foco, setFoco] = useState<string | null>(null);
  const r = 80;
  const circ = 2 * Math.PI * r;
  const gap = fatias.length > 1 ? 3 : 0;
  let acumulado = 0;
  const ativa = fatias.find((c) => c.classe === foco) ?? fatias[0];

  return (
    <div className="rosca">
      <svg viewBox="0 0 200 200" role="img" aria-label={fatias.map((c) => `${c.nome} ${c.pct}%`).join(", ")}>
        <g transform="rotate(-90 100 100)">
          {fatias.map((c) => {
            const tam = (c.pct / 100) * circ;
            const el = (
              <circle
                key={c.classe}
                cx="100" cy="100" r={r} fill="none" stroke={c.cor}
                strokeWidth={foco === c.classe ? 30 : 24}
                strokeDasharray={`${Math.max(tam - gap, 0)} ${circ}`}
                strokeDashoffset={-acumulado}
                onMouseEnter={() => setFoco(c.classe)}
                onMouseLeave={() => setFoco(null)}
                style={{ transition: "stroke-width .15s" }}
              />
            );
            acumulado += tam;
            return el;
          })}
        </g>
        {ativa && (
          <>
            <text x="100" y="98" textAnchor="middle" className="rosca-pct">{ativa.pct}%</text>
            <text x="100" y="120" textAnchor="middle" className="rosca-nome">{ativa.nome}</text>
          </>
        )}
      </svg>
      <ul className="legenda">
        {fatias.map((c) => (
          <li key={c.classe} onMouseEnter={() => setFoco(c.classe)} onMouseLeave={() => setFoco(null)}
              className={foco === c.classe ? "foco" : ""}>
            <span className="ponto" style={{ background: c.cor }} />
            <span className="legenda-nome">{c.nome}</span>
            <span className="legenda-pct">{c.pct}%</span>
            <span className="legenda-mil">R$ {c.por_mil} de cada R$ 1.000</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
