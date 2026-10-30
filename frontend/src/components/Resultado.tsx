import type { CSSProperties } from "react";
import type { Resultado as R } from "../types";
import { Markdown, pct, Rico } from "../texto";
import Notas, { corDa } from "./Notas";

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
      <h1>De cada R$&nbsp;1.000 que você investir</h1>
      <Notas partes={r.carteira} animar />

      <ul className="resumo">
        {r.resumo.map((f) => <li key={f}><Rico texto={f} /></li>)}
      </ul>

      <dl className="fatos">
        <div><dt>Pontuação de suitability</dt><dd>{r.perfil.pontos} de {r.perfil.pontos_max}</dd></div>
        <div><dt>Risco da carteira</dt><dd>{r.risco.rotulo}</dd></div>
        <div><dt>Seu grupo de clientes</dt><dd>{r.segmento.nome}</dd></div>
      </dl>

      {r.avisos.map((a) => <p key={a} className="nota-lateral"><Rico texto={a} /></p>)}

      {r.saude.modo_protecao ? (
        <div className="protecao">
          <h2>Modo proteção ativado</h2>
          <p>Antes de investir com risco, organize a base financeira. Ações, multimercado e previdência ficam de fora por enquanto.</p>
          {r.saude.alertas.length > 0 && <ul>{r.saude.alertas.map((a) => <li key={a}><Rico texto={a} /></li>)}</ul>}
        </div>
      ) : (
        r.saude.alertas.map((a) => <p key={a} className="nota-lateral"><Rico texto={a} /></p>)
      )}

      {r.perfil.limitado_por.length > 0 && (
        <p className="nota-lateral">
          A pontuação indicaria <strong>{r.perfil.pela_soma}</strong>, mas seguimos a resposta mais prudente:{" "}
          {r.perfil.limitado_por.join("; ")}.
        </p>
      )}

      <h2>O que é cada parte</h2>
      <div className="classes">
        {dentro.map((c) => (
          <article key={c.classe} className="classe" style={{ "--cor": corDa(c) } as CSSProperties}>
            <header>
              <h3>{c.nome}</h3>
              <p className="classe-valor">R$ {c.por_mil} <span>({c.pct}%)</span></p>
            </header>
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
        <p className="suave">
          <strong>Fora da carteira:</strong> {fora.map((c) => c.nome).join(", ")}. {fora[0].motivo}
        </p>
      )}

      <details className="sanfona">
        <summary>Como os valores foram calculados</summary>
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
                  <td><span className="amostra" style={{ background: corDa(c) }} aria-hidden /> {c.nome}</td>
                  <td>{c.minimo}%</td><td>{c.maximo}%</td><td>{pct(c.afinidade)}</td><td><strong>{c.pct}%</strong></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>

      <h2>Próximos passos</h2>
      <ol className="passos">
        {r.proximos_passos.map((p) => <li key={p}><p><Rico texto={p} /></p></li>)}
      </ol>

      <h2>Produtos para conhecer</h2>
      {r.produtos.length === 0 ? (
        <p className="nota-lateral">
          {r.saude.modo_protecao
            ? "No modo proteção, o foco é reserva e liquidez antes de novos produtos."
            : "Você já tem os produtos mais comuns para o seu perfil. O foco agora é o rebalanceamento."}
        </p>
      ) : (
        <div className="produtos">
          {r.produtos.map((p) => (
            <article key={p.rotulo} className="produto">
              <h3>{p.rotulo}</h3>
              <p className="suave">{p.classe_br}</p>
              <p className="prob"><strong>{pct(p.prob)}</strong> dos clientes com perfil parecido têm este produto</p>
              <div className="medidor" aria-hidden><span style={{ width: pct(p.prob) }} /></div>
              {p.fatores.length > 0 && (
                <>
                  <p className="pequeno suave">O que mais pesou</p>
                  <ul className="fatores">
                    {p.fatores.map((f) => (
                      <li key={f.texto}>
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

      <h2>Detalhes</h2>
      <details className="sanfona">
        <summary>Seu grupo de clientes: {r.segmento.nome}</summary>
        <p>{r.segmento.descricao}</p>
      </details>
      <details className="sanfona">
        <summary>Por que este perfil</summary>
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
        <p className="suave pequeno">De 0 a 5 pontos, conservador; de 6 a 10, moderado; de 11 a 14, arrojado.</p>
      </details>
      <details className="sanfona">
        <summary>Explicação completa</summary>
        <Markdown texto={r.texto} />
      </details>

      <div className="acoes-finais">
        <button className="botao" onClick={onAjustar}>Ajustar respostas</button>
        <button className="botao" onClick={onRecomecar}>Começar do zero</button>
      </div>

      <p className="aviso-legal">{r.aviso}</p>
    </section>
  );
}
