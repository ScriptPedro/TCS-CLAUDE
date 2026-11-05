import Notas from "./Notas";

interface Props {
  aviso: string;
  onComecar: () => void;
}

const PASSOS = [
  { t: "Responda 14 perguntas", d: "Sobre você, suas finanças, seus objetivos e como você lida com risco. Leva uns 3 minutos." },
  { t: "Compare-se com 50 mil clientes", d: "A IA encontra o grupo de clientes reais mais parecido com você e o que essas pessoas costumam ter." },
  { t: "Receba sua carteira", d: "Quanto colocar em cada tipo de investimento e o motivo de cada valor." },
];

// Persona moderada de reports/personas.md, só para ilustrar o resultado
const EXEMPLO = [
  { classe: "liquidez", nome: "Liquidez diária", pct: 21, por_mil: 210 },
  { classe: "renda_fixa", nome: "Renda fixa", pct: 41, por_mil: 410 },
  { classe: "multimercado", nome: "Multimercado", pct: 11, por_mil: 110 },
  { classe: "acoes", nome: "Ações / ETFs", pct: 20, por_mil: 200 },
  { classe: "previdencia", nome: "Previdência", pct: 7, por_mil: 70 },
];

export default function Inicio({ aviso, onComecar }: Props) {
  return (
    <section className="inicio">
      <h1>Para onde vai cada real que você investe?</h1>
      <p className="lead">
        Responda um questionário curto e veja como dividir cada R$&nbsp;1.000 entre cinco tipos de investimento, com o
        motivo de cada parte.
      </p>
      <button className="botao primario grande" onClick={onComecar}>Começar o questionário</button>

      <Notas partes={EXEMPLO} titulo="Exemplo de resultado para um perfil moderado" />

      <h2>Como funciona</h2>
      <ol className="passos">
        {PASSOS.map((p) => (
          <li key={p.t}>
            <h3>{p.t}</h3>
            <p>{p.d}</p>
          </li>
        ))}
      </ol>
      <p className="suave pequeno">
        Por dentro: segmentação com K-Means, recomendação com LightGBM e explicação com SHAP, sempre limitadas por
        regras de suitability inspiradas na CVM.
      </p>

      <p className="aviso-legal">{aviso}</p>
    </section>
  );
}
