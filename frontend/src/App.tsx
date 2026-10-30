import { useEffect, useRef, useState } from "react";
import { lerResultado } from "./armazenamento";
import Assessor, { type TelaAssessor } from "./components/Assessor";
import Banco from "./components/Banco";
import Icone, { type NomeIcone } from "./components/Icone";
import type { Resultado } from "./types";

// Simulação de um app de banco: a home é cenário e o assessor é a feature do projeto
type Aba = "inicio" | "investir";

const ABAS: { id: Aba | null; icone: NomeIcone; rotulo: string }[] = [
  { id: "inicio", icone: "casa", rotulo: "Início" },
  { id: "investir", icone: "grafico", rotulo: "Investir" },
  { id: null, icone: "pix", rotulo: "Pix" },
  { id: null, icone: "cartao", rotulo: "Cartões" },
  { id: null, icone: "menu", rotulo: "Mais" },
];

export default function App() {
  const [aba, setAba] = useState<Aba>("inicio");
  const [inicialAssessor, setInicialAssessor] = useState<TelaAssessor>("inicio");
  const [resultado, setResultado] = useState<Resultado | null>(lerResultado);
  const [aviso, setAviso] = useState<string | null>(null);
  const timer = useRef<number>();

  useEffect(() => {
    window.scrollTo({ top: 0 });
  }, [aba]);

  const simulado = (recurso: string) => {
    setAviso(`${recurso} é só ilustração neste protótipo. Toque no Assessor de Investimentos.`);
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => setAviso(null), 2600);
  };

  const abrirAssessor = (abrirResultado: boolean) => {
    setInicialAssessor(abrirResultado && resultado ? "resultado" : "inicio");
    setAba("investir");
  };

  return (
    <div className="celular">
      {aba === "inicio" && <Banco resultado={resultado} onAssessor={abrirAssessor} onSimulado={simulado} />}
      {aba === "investir" && (
        <Assessor
          inicial={inicialAssessor}
          resultadoSalvo={resultado}
          onResultado={setResultado}
          onSair={() => setAba("inicio")}
        />
      )}

      {aviso && <div className="aviso-flutuante" role="status">{aviso}</div>}

      <nav className="barra-inferior" aria-label="Navegação principal">
        {ABAS.map((a) => (
          <button
            key={a.rotulo}
            className={a.id === aba ? "ativa" : ""}
            aria-current={a.id === aba ? "page" : undefined}
            onClick={() => (a.id === "investir" ? abrirAssessor(Boolean(resultado)) : a.id ? setAba(a.id) : simulado(a.rotulo))}
          >
            <Icone nome={a.icone} />
            <span>{a.rotulo}</span>
          </button>
        ))}
      </nav>
    </div>
  );
}
