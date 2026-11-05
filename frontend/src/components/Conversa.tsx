import { useEffect, useRef, useState } from "react";
import { ErroApi, buscarInfoConversa, perguntarAssistente } from "../api";
import { Markdown } from "../texto";
import type { InfoConversa, MensagemConversa, Respostas, Simulacao } from "../types";

/** Assessor conversacional (D37): só exibe o que a API devolve; nenhum cálculo aqui. */
export default function Conversa({ respostas }: { respostas: Respostas }) {
  const [info, setInfo] = useState<InfoConversa | null>(null);
  const [mensagens, setMensagens] = useState<MensagemConversa[]>([]);
  const [texto, setTexto] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const fim = useRef<HTMLDivElement>(null);

  useEffect(() => {
    buscarInfoConversa().then(setInfo).catch(() => setInfo(null));
  }, []);

  useEffect(() => {
    if (mensagens.length) fim.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [mensagens, enviando]);

  if (!info) return null;

  if (!info.ativo) {
    return (
      <>
        <h2>Pergunte ao assessor</h2>
        <p className="nota-lateral suave">
          O assistente de conversa está desativado. Para ativar, defina a variável de ambiente GEMINI_API_KEY na API.
        </p>
      </>
    );
  }

  const enviar = async (pergunta: string) => {
    const p = pergunta.trim();
    if (!p || enviando) return;
    const historico = mensagens.map(({ papel, texto }) => ({ papel, texto }));
    setMensagens([...mensagens, { papel: "usuario", texto: p }]);
    setTexto("");
    setErro(null);
    setEnviando(true);
    try {
      const r = await perguntarAssistente(respostas, historico, p);
      setMensagens((ms) => [...ms, { papel: "assistente", texto: r.resposta, simulacoes: r.simulacoes }]);
    } catch (e) {
      setErro(e instanceof ErroApi ? e.message : "Não foi possível falar com o assistente.");
      setMensagens((ms) => ms.slice(0, -1));
      setTexto(p);
    } finally {
      setEnviando(false);
    }
  };

  return (
    <section className="conversa" aria-label="Conversa com o assessor">
      <h2>Pergunte ao assessor</h2>
      <p className="suave pequeno">{info.aviso}</p>

      {mensagens.length === 0 && (
        <div className="chips sugestoes">
          {info.sugestoes.map((s) => (
            <button type="button" key={s} className="chip" onClick={() => enviar(s)} disabled={enviando}>{s}</button>
          ))}
        </div>
      )}

      <div className="mensagens" aria-live="polite">
        {mensagens.map((m, i) => (
          <div key={i} className={`mensagem ${m.papel}`}>
            {m.papel === "assistente" ? <Markdown texto={m.texto} /> : <p>{m.texto}</p>}
            {m.simulacoes?.map((s, j) => <TabelaSimulacao key={j} s={s} />)}
          </div>
        ))}
        {enviando && <div className="mensagem assistente pensando">Pensando…</div>}
        <div ref={fim} />
      </div>

      {erro && <p className="erro" role="alert">{erro}</p>}

      <form
        className="caixa-pergunta"
        onSubmit={(e) => {
          e.preventDefault();
          enviar(texto);
        }}
      >
        <label htmlFor="pergunta" className="visualmente-oculto">Sua pergunta</label>
        <input
          id="pergunta"
          value={texto}
          maxLength={info.max_caracteres}
          placeholder="Ex.: o que muda se eu quitar o cartão?"
          onChange={(e) => setTexto(e.target.value)}
          disabled={enviando}
          autoComplete="off"
        />
        <button className="botao primario" disabled={enviando || !texto.trim()}>Enviar</button>
      </form>
    </section>
  );
}

function TabelaSimulacao({ s }: { s: Simulacao }) {
  const mudancas = Object.entries(s.mudancas).map(([k, v]) => `${k} ${v}`).join(" · ");
  return (
    <div className="simulacao">
      <p className="pequeno"><strong>Cenário simulado:</strong> {mudancas}</p>
      <p className="pequeno">
        Perfil {s.perfil_antes} → {s.perfil_depois}
        {s.modo_protecao_antes !== s.modo_protecao_depois &&
          ` · modo proteção ${s.modo_protecao_depois ? "ativado" : "desativado"}`}
      </p>
      <div className="tabela-rolagem">
        <table>
          <thead><tr><th>Classe</th><th>Hoje</th><th>No cenário</th></tr></thead>
          <tbody>
            {s.carteira.map((c) => (
              <tr key={c.classe}><td>{c.nome}</td><td>{c.antes}%</td><td><strong>{c.depois}%</strong></td></tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
