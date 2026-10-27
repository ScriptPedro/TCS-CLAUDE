interface Props {
  aviso: string;
  onComecar: () => void;
}

const PASSOS = [
  { n: "1", t: "Responda 14 perguntas", d: "Sobre você, suas finanças, objetivos e como lida com risco. Leva uns 3 minutos." },
  { n: "2", t: "A IA compara você", d: "Com 50 mil clientes reais: em que grupo você se encaixa e o que pessoas parecidas têm." },
  { n: "3", t: "Receba sua carteira", d: "Quanto colocar em cada tipo de investimento, e o porquê de cada número." },
];

export default function Inicio({ aviso, onComecar }: Props) {
  return (
    <section className="inicio">
      <div className="hero">
        <p className="sobretitulo">Assessor de Investimentos Virtual</p>
        <h1>Descubra seu perfil e uma carteira feita para você</h1>
        <p className="lead">
          Segmentação com K-Means, recomendação com LightGBM e explicação com SHAP. Tudo passa por regras de
          suitability inspiradas na CVM.
        </p>
        <button className="botao primario grande" onClick={onComecar}>
          Começar agora <span aria-hidden>→</span>
        </button>
      </div>

      <ol className="passos-intro">
        {PASSOS.map((p) => (
          <li key={p.n} className="cartao">
            <span className="numero">{p.n}</span>
            <h3>{p.t}</h3>
            <p>{p.d}</p>
          </li>
        ))}
      </ol>

      <p className="aviso-legal">
        <span aria-hidden>⚠️</span> {aviso}
      </p>
    </section>
  );
}
