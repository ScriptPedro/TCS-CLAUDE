import type { CSSProperties } from "react";
import type { Resultado as R } from "../types";
import { capitalizar, Markdown, pct, Rico } from "../texto";
import Rosca from "./Rosca";

interface Props {
  r: R;
  onAjustar: () => void;
  onRecomecar: () => void;
}

export default function Resultado({ r, onAjustar, onRecomecar }: Props) {
  const dentro = r.carteira.filter((c) => c.pct > 0);
  const fora = r.carteira.filter((c) => c.pct === 0);
  const perfil = r.perfil.efetivo;

  return (
    <section className="resultado">
      <div className={`cartao destaque perfil-${perfil}`}>
        <p className="sobretitulo">Seu perfil de investidor</p>
        <h1>{capitalizar(perfil)}</h1>
        <ul className="resumo">
          {r.resumo.map((f) => <li key={f}><Rico texto={f} /></li>)}
        </ul>
        <div className="metricas">
          <Metrica rotulo="Pontuação" valor={`${r.perfil.pontos} / ${r.perfil.pontos_max}`}
                   barra={r.perfil.pontos / r.perfil.pontos_max} />
          <Metrica rotulo="Risco da carteira" valor={r.risco.rotulo} />
          <Metrica rotulo="Seu grupo de clientes" valor={r.segmento.nome} pequeno />
        </div>
      </div>

      {r.avisos.map((a) => <div key={a} className="alerta info"><Rico texto={a} /></div>)}

      {r.saude.modo_protecao ? (
        <div className="alerta protecao">
          <h3>🛡️ Modo proteção ativado</h3>
          <p>Antes de investir com risco, organize a base financeira. Ações, multimercado e previdência ficam de fora por enquanto.</p>
          {r.saude.alertas.length > 0 && <ul>{r.saude.alertas.map((a) => <li key={a}><Rico texto={a} /></li>)}</ul>}
        </div>
      ) : (
        r.saude.alertas.map((a) => <div key={a} className="alerta info"><Rico texto={a} /></div>)
      )}

      {r.perfil.limitado_por.length > 0 && (
        <div className="alerta info">
          A pontuação indicaria <strong>{r.perfil.pela_soma}</strong>, mas seguimos a resposta mais prudente:{" "}
          {r.perfil.limitado_por.join("; ")}.
        </div>
      )}

      <h2 className="secao">Sua carteira sugerida</h2>
      <div className="cartao">
        <Rosca classes={r.carteira} />
      </div>

      <div className="grade-classes">
        {dentro.map((c) => (
          <article key={c.classe} className="cartao classe" style={{ "--cor": c.cor } as CSSProperties}>
            <header>
              <span className="classe-pct">{c.pct}%</span>
              <h3>{c.nome}</h3>
            </header>
            <div className="barra" aria-hidden><span style={{ width: `${c.pct}%` }} /></div>
            <p className="mil">R$ {c.por_mil} de cada R$ 1.000 investidos</p>
            <p>{c.o_que_e}</p>
            <p><strong>Para que serve:</strong> {c.papel}</p>
            <dl className="ficha">
              <div><dt>Risco</dt><dd>{c.risco}</dd></div>
              <div><dt>Resgate</dt><dd>{c.resgate}</dd></div>
            </dl>
            <p className="motivo"><strong>Por que {c.pct}%?</strong> {c.motivo}</p>
          </article>
        ))}
      </div>

      {fora.length > 0 && (
        <p className="suave fora">
          <strong>Fora da carteira:</strong> {fora.map((c) => c.nome).join(", ")}. {fora[0].motivo}
        </p>
      )}

      <details className="cartao sanfona">
        <summary>Como os números foram calculados</summary>
        <ol>
          <li>Suas respostas definem o perfil <strong>{perfil}</strong>, e o perfil define o mínimo e o máximo de cada classe.</li>
          <li>Cada classe começa no mínimo.</li>
          <li>O espaço que sobra vai para as classes mais comuns entre clientes parecidos com você (afinidade estimada pelo modelo de IA), sem passar do máximo.</li>
        </ol>
        <div className="tabela-rolagem">
          <table>
            <thead><tr><th>Classe</th><th>Mínimo</th><th>Máximo</th><th>Afinidade do modelo</th><th>Final</th></tr></thead>
            <tbody>
              {r.carteira.map((c) => (
                <tr key={c.classe}>
                  <td><span className="ponto" style={{ background: c.cor }} /> {c.nome}</td>
                  <td>{c.minimo}%</td><td>{c.maximo}%</td><td>{pct(c.afinidade)}</td><td><strong>{c.pct}%</strong></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>

      <h2 className="secao">Próximos passos</h2>
      <ol className="linha-tempo">
        {r.proximos_passos.map((p, i) => (
          <li key={p}><span className="bolinha">{i + 1}</span><p><Rico texto={p} /></p></li>
        ))}
      </ol>

      <h2 className="secao">Produtos para conhecer</h2>
      {r.produtos.length === 0 ? (
        <div className="alerta info">
          {r.saude.modo_protecao
            ? "No modo proteção, o foco é reserva e liquidez antes de novos produtos."
            : "Você já tem os produtos mais comuns para o seu perfil. O foco agora é o rebalanceamento."}
        </div>
      ) : (
        <div className="grade-produtos">
          {r.produtos.map((p) => (
            <article key={p.rotulo} className="cartao produto">
              <h3>{p.rotulo}</h3>
              <p className="suave">{p.classe_br}</p>
              <div className="prob">
                <span className="prob-num">{pct(p.prob)}</span>
                <span className="suave">dos clientes com perfil parecido têm</span>
              </div>
              <div className="barra" aria-hidden><span style={{ width: pct(p.prob) }} /></div>
              {p.fatores.length > 0 && (
                <>
                  <p className="pequeno">O que mais pesou</p>
                  <ul className="fatores">
                    {p.fatores.map((f) => (
                      <li key={f.texto} className={f.direcao}>
                        <span aria-label={f.direcao === "alta" ? "aumenta" : "diminui"}>{f.direcao === "alta" ? "↑" : "↓"}</span>
                        {f.texto}
                      </li>
                    ))}
                  </ul>
                </>
              )}
            </article>
          ))}
        </div>
      )}

      <h2 className="secao">Detalhes</h2>
      <details className="cartao sanfona">
        <summary>Seu grupo de clientes: {r.segmento.nome}</summary>
        <p>{r.segmento.descricao}</p>
      </details>
      <details className="cartao sanfona">
        <summary>Por que este perfil? (pontuação de suitability)</summary>
        <div className="tabela-rolagem">
          <table>
            <thead><tr><th>Pergunta</th><th>Sua resposta</th><th>Pontos</th></tr></thead>
            <tbody>
              {r.perfil.detalhamento.map((d) => (
                <tr key={d.pergunta}><td>{d.pergunta}</td><td>{d.resposta}</td><td>{d.pontos}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="suave pequeno">0–5 conservador · 6–10 moderado · 11–14 arrojado</p>
      </details>
      <details className="cartao sanfona">
        <summary>Explicação completa</summary>
        <Markdown texto={r.texto} />
      </details>

      <div className="acoes-finais">
        <button className="botao" onClick={onAjustar}>✏️ Ajustar respostas</button>
        <button className="botao" onClick={onRecomecar}>↩ Começar do zero</button>
      </div>

      <p className="aviso-legal"><span aria-hidden>⚠️</span> {r.aviso}</p>
    </section>
  );
}

function Metrica({ rotulo, valor, barra, pequeno }: { rotulo: string; valor: string; barra?: number; pequeno?: boolean }) {
  return (
    <div className="metrica">
      <span className="metrica-rotulo">{rotulo}</span>
      <span className={`metrica-valor ${pequeno ? "pequeno" : ""}`}>{valor}</span>
      {barra !== undefined && <div className="barra fina" aria-hidden><span style={{ width: `${barra * 100}%` }} /></div>}
    </div>
  );
}
