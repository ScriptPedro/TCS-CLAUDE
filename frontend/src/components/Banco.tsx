import { useState } from "react";
import { capitalizar } from "../texto";
import type { Resultado } from "../types";
import Icone, { type NomeIcone } from "./Icone";
import Notas from "./Notas";

interface Props {
  resultado: Resultado | null;
  onAssessor: (abrirResultado: boolean) => void;
  onSimulado: (recurso: string) => void;
}

// Tudo nesta tela é cenário fictício do app do banco; só o card do assessor leva a uma feature real
const CLIENTE = "Ana";
const SALDO = 4218.37;
const INVESTIDO = 12540.0;
const FATURA = { valor: 1326.9, vence: "10 nov", limite: 6000, usado: 2480 };

const ATALHOS: { icone: NomeIcone; rotulo: string }[] = [
  { icone: "pix", rotulo: "Pix" },
  { icone: "codigoBarras", rotulo: "Pagar" },
  { icone: "transferir", rotulo: "Transferir" },
  { icone: "depositar", rotulo: "Depositar" },
  { icone: "celular", rotulo: "Recarga" },
  { icone: "emprestimo", rotulo: "Empréstimo" },
];

const EXTRATO = [
  { icone: "entrada" as const, desc: "Pix de Marcos L.", quando: "Hoje", valor: 150 },
  { icone: "mercado" as const, desc: "Supermercado Bom Preço", quando: "Hoje", valor: -87.42 },
  { icone: "saida" as const, desc: "Conta de luz", quando: "Ontem", valor: -142.1 },
  { icone: "entrada" as const, desc: "Salário", quando: "28 out", valor: 5200 },
];

const reais = (v: number) => v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

export default function Banco({ resultado, onAssessor, onSimulado }: Props) {
  const [oculto, setOculto] = useState(false);
  const valor = (v: number) => (oculto ? "R$ ••••" : reais(v));

  return (
    <div className="tela-banco">
      <header className="banco-topo">
        <div className="banco-saudacao">
          <span className="avatar" aria-hidden>{CLIENTE[0]}</span>
          <div>
            <p className="banco-ola">Olá, {CLIENTE}</p>
            <p className="banco-agencia">Ag 0001 · Cc 12345-6</p>
          </div>
        </div>
        <div className="banco-icones">
          <button className="botao-barra" onClick={() => setOculto(!oculto)} aria-label={oculto ? "Mostrar valores" : "Esconder valores"}>
            <Icone nome={oculto ? "olhoFechado" : "olho"} />
          </button>
          <button className="botao-barra" onClick={() => onSimulado("Ajuda")} aria-label="Ajuda"><Icone nome="ajuda" /></button>
          <button className="botao-barra" onClick={() => onSimulado("Notificações")} aria-label="Notificações"><Icone nome="sino" /></button>
        </div>
      </header>

      <main className="banco-conteudo">
        <section className="cartao-bloco saldo">
          <p className="rotulo">Saldo em conta</p>
          <p className="valor-grande">{valor(SALDO)}</p>
          <button className="link" onClick={() => onSimulado("Extrato")}>Ver extrato <Icone nome="seta" tamanho={16} /></button>
        </section>

        <nav className="atalhos" aria-label="Atalhos">
          {ATALHOS.map((a) => (
            <button key={a.rotulo} className="atalho" onClick={() => onSimulado(a.rotulo)}>
              <span className="atalho-icone"><Icone nome={a.icone} /></span>
              {a.rotulo}
            </button>
          ))}
        </nav>

        <article className="card-assessor">
          <p className="etiqueta"><Icone nome="brilho" tamanho={16} /> Novo · Inteligência artificial</p>
          <h2>Assessor de Investimentos Virtual</h2>
          {resultado ? (
            <>
              <p>
                Sua carteira sugerida, perfil <strong>{resultado.perfil.efetivo}</strong>. De cada R$&nbsp;1.000:
              </p>
              <Notas partes={resultado.carteira} />
              <div className="card-acoes">
                <button className="botao primario" onClick={() => onAssessor(true)}>Ver minha carteira</button>
                <button className="botao" onClick={() => onAssessor(false)}>Refazer</button>
              </div>
            </>
          ) : (
            <>
              <p>
                Responda 14 perguntas e descubra como dividir cada R$&nbsp;1.000 entre cinco tipos de investimento,
                com o motivo de cada parte.
              </p>
              <button className="botao primario" onClick={() => onAssessor(false)}>Descobrir minha carteira</button>
            </>
          )}
        </article>

        <section className="cartao-bloco">
          <button className="bloco-cabeca" onClick={() => onAssessor(Boolean(resultado))}>
            <span><Icone nome="grafico" /> Investimentos</span>
            <Icone nome="seta" />
          </button>
          <p className="valor-medio">{valor(INVESTIDO)}</p>
          <p className="suave pequeno">
            {resultado
              ? `Risco da carteira sugerida: ${capitalizar(resultado.risco.rotulo)}`
              : "Ainda não sabe onde investir? Peça ajuda ao assessor virtual."}
          </p>
        </section>

        <section className="cartao-bloco">
          <button className="bloco-cabeca" onClick={() => onSimulado("Cartão de crédito")}>
            <span><Icone nome="cartao" /> Cartão de crédito</span>
            <Icone nome="seta" />
          </button>
          <p className="rotulo">Fatura atual · vence {FATURA.vence}</p>
          <p className="valor-medio">{valor(FATURA.valor)}</p>
          <div className="medidor" aria-hidden><span style={{ width: `${(FATURA.usado / FATURA.limite) * 100}%` }} /></div>
          <p className="suave pequeno">Limite disponível: {valor(FATURA.limite - FATURA.usado)}</p>
        </section>

        <section className="cartao-bloco">
          <p className="bloco-titulo">Últimas movimentações</p>
          <ul className="extrato">
            {EXTRATO.map((m) => (
              <li key={m.desc}>
                <span className="extrato-icone"><Icone nome={m.icone} tamanho={20} /></span>
                <span className="extrato-desc">{m.desc}<small>{m.quando}</small></span>
                <span className={m.valor > 0 ? "extrato-valor positivo" : "extrato-valor"}>
                  {oculto ? "••••" : `${m.valor > 0 ? "+" : "−"} ${reais(Math.abs(m.valor))}`}
                </span>
              </li>
            ))}
          </ul>
        </section>

        <p className="suave pequeno centro">Banco Cédula é um banco fictício, criado para demonstrar a feature.</p>
      </main>
    </div>
  );
}
