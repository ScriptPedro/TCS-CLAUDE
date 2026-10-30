import { useEffect, useState } from "react";
import { buscarQuestionario, ErroApi, pedirRecomendacao } from "./api";
import Inicio from "./components/Inicio";
import Questionario from "./components/Questionario";
import Resultado from "./components/Resultado";
import type { Questionario as Q, Respostas, Resultado as R } from "./types";

type Tela = "inicio" | "questionario" | "resultado";
const CHAVE = "assessor.respostas";

// As respostas ficam no navegador para sobreviver a um recarregamento (conveniência, não dado oficial)
function lerSalvas(): Respostas | null {
  try {
    return JSON.parse(localStorage.getItem(CHAVE) ?? "null");
  } catch {
    return null;
  }
}
function salvar(r: Respostas | null) {
  try {
    if (r) localStorage.setItem(CHAVE, JSON.stringify(r));
    else localStorage.removeItem(CHAVE);
  } catch {
    /* armazenamento indisponível: segue sem salvar */
  }
}

export default function App() {
  const [questionario, setQuestionario] = useState<Q | null>(null);
  const [erroCarga, setErroCarga] = useState<string | null>(null);
  const [tela, setTela] = useState<Tela>("inicio");
  const [etapa, setEtapa] = useState(0);
  const [respostas, setRespostas] = useState<Respostas>({});
  const [resultado, setResultado] = useState<R | null>(null);
  const [erros, setErros] = useState<string[]>([]);
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    buscarQuestionario()
      .then((q) => {
        setQuestionario(q);
        setRespostas({ ...q.padrao, ...(lerSalvas() ?? {}) });
      })
      .catch((e: ErroApi) => setErroCarga(e.message));
  }, []);

  useEffect(() => {
    window.scrollTo({ top: 0, behavior: "smooth" });
  }, [tela, etapa]);

  const responder = (campo: string, valor: Respostas[string]) => {
    const novas = { ...respostas, [campo]: valor };
    setRespostas(novas);
    salvar(novas);
  };

  const enviar = async () => {
    setEnviando(true);
    setErros([]);
    try {
      setResultado(await pedirRecomendacao(respostas));
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
    salvar(null);
    if (questionario) setRespostas({ ...questionario.padrao });
    setResultado(null);
    setEtapa(0);
    setTela("inicio");
  };

  return (
    <div className="app">
      <header className="topo">
        <button className="marca" onClick={recomecar} aria-label="Voltar ao início">
          <img src="/favicon.svg" alt="" width={24} height={24} />
          <span>Assessor de Investimentos</span>
        </button>
        <span className="selo">Projeto acadêmico de IA Aplicada</span>
      </header>

      <main className="conteudo">
        {erroCarga && (
          <div className="erro" role="alert">
            <p><strong>O questionário não carregou.</strong> {erroCarga}</p>
            <p>Inicie a API na raiz do projeto:</p>
            <pre>uvicorn api.main:app --port 8000</pre>
          </div>
        )}
        {!erroCarga && !questionario && <p className="carregando">Carregando o questionário…</p>}
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
      </main>

      <footer className="rodape">
        Modelos treinados com dados do Santander Product Recommendation (Kaggle). Não é recomendação de investimento.
      </footer>
    </div>
  );
}
