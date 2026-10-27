import type { CSSProperties } from "react";
import type { Etapa, Pergunta, Respostas, Valor } from "../types";

interface Props {
  etapas: Etapa[];
  etapa: number;
  respostas: Respostas;
  erros: string[];
  enviando: boolean;
  onResponder: (campo: string, valor: Valor) => void;
  onEtapa: (i: number) => void;
  onEnviar: () => void;
}

export default function Questionario({ etapas, etapa, respostas, erros, enviando, onResponder, onEtapa, onEnviar }: Props) {
  const atual = etapas[etapa];
  const ultima = etapa === etapas.length - 1;

  return (
    <section className="questionario">
      <ol className="stepper" aria-label="Etapas">
        {etapas.map((e, i) => (
          <li key={e.titulo} className={i === etapa ? "ativa" : i < etapa ? "feita" : ""}>
            <button onClick={() => i < etapa && onEtapa(i)} disabled={i > etapa} aria-current={i === etapa ? "step" : undefined}>
              <span className="bolinha">{i < etapa ? "✓" : i + 1}</span>
              <span className="rotulo-etapa">{e.titulo}</span>
            </button>
          </li>
        ))}
      </ol>

      <div className="cartao etapa">
        <header>
          <p className="sobretitulo">Etapa {etapa + 1} de {etapas.length}</p>
          <h2>{atual.titulo}</h2>
          <p className="suave">{atual.descricao}</p>
        </header>

        {atual.perguntas.map((p) => (
          <Campo key={p.campo} p={p} valor={respostas[p.campo]} onChange={(v) => onResponder(p.campo, v)} />
        ))}

        {erros.length > 0 && (
          <div className="alerta erro" role="alert">
            {erros.map((e) => <p key={e}>{e}</p>)}
          </div>
        )}

        <footer className="navegacao">
          {etapa > 0 ? (
            <button className="botao" onClick={() => onEtapa(etapa - 1)}>← Voltar</button>
          ) : <span />}
          {ultima ? (
            <button className="botao primario" onClick={onEnviar} disabled={enviando}>
              {enviando ? "Calculando…" : "Ver minha recomendação"}
            </button>
          ) : (
            <button className="botao primario" onClick={() => onEtapa(etapa + 1)}>Avançar →</button>
          )}
        </footer>
      </div>
    </section>
  );
}

function Campo({ p, valor, onChange }: { p: Pergunta; valor: Valor; onChange: (v: Valor) => void }) {
  const id = `q-${p.campo}`;
  return (
    <fieldset className="pergunta">
      <legend id={id}>{p.texto}</legend>
      {p.ajuda && <p className="ajuda">{p.ajuda}</p>}
      {p.tipo === "numero" && <Numero valor={Number(valor)} onChange={onChange} rotulo={id} />}
      {p.tipo === "opcao" && <Opcoes p={p} valor={String(valor)} onChange={onChange} />}
      {p.tipo === "faixa" && <Faixa p={p} valor={String(valor)} onChange={onChange} rotulo={id} />}
      {p.tipo === "multipla" && <Multipla p={p} valor={(valor as string[]) ?? []} onChange={onChange} />}
    </fieldset>
  );
}

function Numero({ valor, onChange, rotulo }: { valor: number; onChange: (v: number) => void; rotulo: string }) {
  const ajustar = (v: number) => onChange(Math.min(100, Math.max(18, v)));
  return (
    <div className="numero-campo">
      <button type="button" className="botao icone" onClick={() => ajustar(valor - 1)} aria-label="Diminuir">−</button>
      <input
        type="number" inputMode="numeric" min={18} max={100} value={Number.isNaN(valor) ? "" : valor}
        aria-labelledby={rotulo}
        onChange={(e) => onChange(e.target.value === "" ? NaN : Number(e.target.value))}
        onBlur={() => !Number.isNaN(valor) && ajustar(valor)}
      />
      <span className="sufixo">anos</span>
      <button type="button" className="botao icone" onClick={() => ajustar(valor + 1)} aria-label="Aumentar">+</button>
    </div>
  );
}

function Opcoes({ p, valor, onChange }: { p: Pergunta; valor: string; onChange: (v: string) => void }) {
  return (
    <div className={`opcoes ${p.horizontal ? "horizontal" : ""}`} role="radiogroup">
      {p.opcoes.map((o) => (
        <label key={o.valor} className={`opcao ${valor === o.valor ? "marcada" : ""}`}>
          <input type="radio" name={p.campo} value={o.valor} checked={valor === o.valor} onChange={() => onChange(o.valor)} />
          <span className="radio" aria-hidden />
          <span>{o.rotulo}</span>
        </label>
      ))}
    </div>
  );
}

function Faixa({ p, valor, onChange, rotulo }: { p: Pergunta; valor: string; onChange: (v: string) => void; rotulo: string }) {
  const i = Math.max(0, p.opcoes.findIndex((o) => o.valor === valor));
  const n = p.opcoes.length - 1;
  return (
    <div className="faixa" style={{ "--progresso": `${(i / n) * 100}%` } as CSSProperties}>
      <output className="faixa-valor">{p.opcoes[i].rotulo}</output>
      <input
        type="range" min={0} max={n} step={1} value={i} aria-labelledby={rotulo}
        aria-valuetext={p.opcoes[i].rotulo}
        onChange={(e) => onChange(p.opcoes[Number(e.target.value)].valor)}
      />
      <div className="faixa-marcas">
        {p.opcoes.map((o, j) => (
          <button type="button" key={o.valor} className={j === i ? "ativa" : ""} onClick={() => onChange(o.valor)}>
            {o.rotulo}
          </button>
        ))}
      </div>
    </div>
  );
}

function Multipla({ p, valor, onChange }: { p: Pergunta; valor: string[]; onChange: (v: string[]) => void }) {
  const alternar = (v: string) => onChange(valor.includes(v) ? valor.filter((x) => x !== v) : [...valor, v]);
  return (
    <div className="chips">
      {p.opcoes.map((o) => {
        const on = valor.includes(o.valor);
        return (
          <button type="button" key={o.valor} className={`chip ${on ? "on" : ""}`} aria-pressed={on} onClick={() => alternar(o.valor)}>
            <span aria-hidden>{on ? "✓" : "+"}</span> {o.rotulo}
          </button>
        );
      })}
    </div>
  );
}
