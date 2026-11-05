import { useEffect, useState } from "react";
import { buscarQuestionario, ErroApi, pedirRecomendacao } from "../api";
import { lerRespostas, salvarRespostas, salvarResultado } from "../armazenamento";
import type { Questionario as Q, Respostas, Resultado as R } from "../types";
import Icone from "./Icone";
import Inicio from "./Inicio";
import Questionario from "./Questionario";
import Resultado from "./Resultado";

export type TelaAssessor = "inicio" | "questionario" | "resultado";

interface Props {
  /** Abre direto no último resultado salvo (vindo do card da home) ou na apresentação. */
  inicial: TelaAssessor;
  resultadoSalvo: R | null;
  onResultado: (r: R | null) => void;
  onSair: () => void;
}

/** A feature do assessor dentro do app do banco: mesmo fluxo de antes, agora como uma tela com barra de voltar. */
export default function Assessor({ inicial, resultadoSalvo, onResultado, onSair }: Props) {
  const [questionario, setQuestionario] = useState<Q | null>(null);
  const [erroCarga, setErroCarga] = useState<string | null>(null);
  const [tela, setTela] = useState<TelaAssessor>(inicial === "resultado" && !resultadoSalvo ? "inicio" : inicial);
  const [etapa, setEtapa] = useState(0);
  const [respostas, setRespostas] = useState<Respostas>({});
  const [resultado, setResultado] = useState<R | null>(resultadoSalvo);
  const [erros, setErros] = useState<string[]>([]);
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    buscarQuestionario()
      .then((q) => {
        setQuestionario(q);
        setRespostas({ ...q.padrao, ...(lerRespostas() ?? {}) });
      })
      .catch((e: ErroApi) => setErroCarga(e.message));
  }, []);

  useEffect(() => {
    window.scrollTo({ top: 0, behavior: "smooth" });
  }, [tela, etapa]);

  const responder = (campo: string, valor: Respostas[string]) => {
    const novas = { ...respostas, [campo]: valor };
    setRespostas(novas);
    salvarRespostas(novas);
  };

  const enviar = async () => {
    setEnviando(true);
    setErros([]);
    try {
      const r = await pedirRecomendacao(respostas);
      setResultado(r);
      salvarResultado(r);
      onResultado(r);
      setTela("resultado");
    } catch (e) {
      setErros(e instanceof ErroApi ? e.erros : ["Erro inesperado. Tente novamente."]);
    } finally {
      setEnviando(false);
    }
  };

  const ajustar = () => {
    setEtapa(0);
    setTela("questionario");
  };
  const recomecar = () => {
    salvarRespostas(null);
    salvarResultado(null);
    onResultado(null);
    if (questionario) setRespostas({ ...questionario.padrao });
    setResultado(null);
    setEtapa(0);
    setTela("inicio");
  };

  // Voltar como num app: um nível por toque, até sair para a home do banco
  const voltar = () => {
    if (tela === "questionario" && etapa > 0) setEtapa(etapa - 1);
    else if (tela === "questionario") setTela("inicio");
    else onSair();
  };

  // O resultado salvo aparece mesmo sem a API no ar; o resto do fluxo precisa dela
  const precisaApi = tela !== "resultado" || !resultado;

  return (
    <div className="tela-assessor">
      <header className="barra-app">
        <button className="botao-barra" onClick={voltar} aria-label="Voltar">
          <Icone nome="voltar" />
        </button>
        <div className="barra-titulo">
          <span>Assessor de Investimentos</span>
          <small>Virtual · IA</small>
        </div>
        <span className="botao-barra" aria-hidden />
      </header>

      <main className="conteudo">
        {precisaApi && erroCarga && (
          <div className="erro" role="alert">
            <p><strong>O questionário não carregou.</strong> {erroCarga}</p>
            <p>Inicie a API na raiz do projeto:</p>
            <pre>uvicorn api.main:app --port 8000</pre>
          </div>
        )}
        {precisaApi && !erroCarga && !questionario && <p className="carregando">Carregando o questionário…</p>}
        {questionario && tela === "inicio" && <Inicio aviso={questionario.aviso} onComecar={() => setTela("questionario")} />}
        {questionario && tela === "questionario" && (
          <Questionario
            etapas={questionario.etapas}
            etapa={etapa}
            respostas={respostas}
            erros={erros}
            enviando={enviando}
            onResponder={responder}
            onEtapa={setEtapa}
            onEnviar={enviar}
          />
        )}
        {resultado && tela === "resultado" && <Resultado r={resultado} onAjustar={ajustar} onRecomecar={recomecar} />}

        <p className="rodape">
          Modelos treinados com dados do Santander Product Recommendation (Kaggle). Projeto acadêmico de IA Aplicada.
          Não é recomendação de investimento.
        </p>
      </main>
    </div>
  );
}
