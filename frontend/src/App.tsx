import { useCallback, useEffect, useRef, useState } from "react";
import { buscarRegras, quandoSessaoExpirar, quemSouEu, sair } from "./api";
import { lerResultado, lerToken, salvarRespostas, salvarResultado, salvarToken } from "./armazenamento";
import Assessor, { type TelaAssessor } from "./components/Assessor";
import Banco from "./components/Banco";
import Conta from "./components/Conta";
import Entrar from "./components/Entrar";
import Icone, { type NomeIcone } from "./components/Icone";
import Usuarios from "./components/Usuarios";
import type { Regras, Resultado, Sessao, Usuario } from "./types";

// Simulação de um app de banco: a home é cenário e o assessor é a feature do projeto.
// Só entra quem fez login (D40); a aba "Conta" leva ao gerenciamento de usuários dos administradores.
type Aba = "inicio" | "investir" | "conta" | "usuarios";

const ABAS: { id: Aba | null; icone: NomeIcone; rotulo: string }[] = [
  { id: "inicio", icone: "casa", rotulo: "Início" },
  { id: "investir", icone: "grafico", rotulo: "Investir" },
  { id: null, icone: "pix", rotulo: "Pix" },
  { id: null, icone: "cartao", rotulo: "Cartões" },
  { id: "conta", icone: "usuario", rotulo: "Conta" },
];

export default function App() {
  const [usuario, setUsuario] = useState<Usuario | null>(null);
  const [verificando, setVerificando] = useState(() => Boolean(lerToken()));
  const [regras, setRegras] = useState<Regras | null>(null);
  const [aba, setAba] = useState<Aba>("inicio");
  const [inicialAssessor, setInicialAssessor] = useState<TelaAssessor>("inicio");
  const [resultado, setResultado] = useState<Resultado | null>(lerResultado);
  const [aviso, setAviso] = useState<string | null>(null);
  const timer = useRef<number>();

  const avisar = (texto: string) => {
    setAviso(texto);
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => setAviso(null), 2600);
  };

  // Ao sair, o resultado e as respostas salvos no aparelho também saem: são da pessoa, não do aparelho
  const encerrar = useCallback(() => {
    salvarToken(null);
    salvarResultado(null);
    salvarRespostas(null);
    setResultado(null);
    setUsuario(null);
    setAba("inicio");
  }, []);

  useEffect(() => {
    quandoSessaoExpirar(() => {
      encerrar();
      avisar("Sua sessão expirou. Entre de novo.");
    });
    buscarRegras().then(setRegras).catch(() => setRegras(null));
    if (lerToken()) {
      quemSouEu()
        .then(setUsuario)
        .catch(() => salvarToken(null))
        .finally(() => setVerificando(false));
    }
  }, [encerrar]);

  useEffect(() => {
    window.scrollTo({ top: 0 });
  }, [aba]);

  const entrou = ({ token, usuario: u }: Sessao) => {
    salvarToken(token);
    setUsuario(u);
    setAba("inicio");
  };

  const sairDaConta = async () => {
    await sair().catch(() => undefined); // mesmo sem a API, a sessão local é apagada
    encerrar();
  };

  const abrirAssessor = (abrirResultado: boolean) => {
    setInicialAssessor(abrirResultado && resultado ? "resultado" : "inicio");
    setAba("investir");
  };

  if (verificando) {
    return <div className="celular"><p className="carregando centro">Carregando…</p></div>;
  }

  if (!usuario) {
    return (
      <div className="celular sem-barra">
        <Entrar regras={regras} onEntrou={entrou} />
        {aviso && <div className="aviso-flutuante" role="status">{aviso}</div>}
      </div>
    );
  }

  const primeiroNome = usuario.nome.split(" ")[0];

  return (
    <div className="celular">
      {aba === "inicio" && (
        <Banco cliente={primeiroNome} resultado={resultado} onAssessor={abrirAssessor}
          onSimulado={(r) => avisar(`${r} é só ilustração neste protótipo. Toque no Assessor de Investimentos.`)} />
      )}
      {aba === "investir" && (
        <Assessor
          inicial={inicialAssessor}
          resultadoSalvo={resultado}
          onResultado={setResultado}
          onSair={() => setAba("inicio")}
        />
      )}
      {aba === "conta" && <Conta usuario={usuario} onUsuarios={() => setAba("usuarios")} onSair={sairDaConta} />}
      {aba === "usuarios" && usuario.papel === "admin" && (
        <Usuarios eu={usuario} regras={regras} onSair={() => setAba("conta")} />
      )}

      {aviso && <div className="aviso-flutuante" role="status">{aviso}</div>}

      <nav className="barra-inferior" aria-label="Navegação principal">
        {ABAS.map((a) => {
          const ativa = a.id === aba || (a.id === "conta" && aba === "usuarios");
          return (
            <button
              key={a.rotulo}
              className={ativa ? "ativa" : ""}
              aria-current={ativa ? "page" : undefined}
              onClick={() => (a.id === "investir" ? abrirAssessor(Boolean(resultado)) : a.id ? setAba(a.id) : avisar(`${a.rotulo} é só ilustração neste protótipo. Toque no Assessor de Investimentos.`))}
            >
              <Icone nome={a.icone} />
              <span>{a.rotulo}</span>
            </button>
          );
        })}
      </nav>
    </div>
  );
}
