// Contrato com api/main.py

export type Valor = string | number | string[];
export type Respostas = Record<string, Valor>;

export interface Opcao {
  valor: string;
  rotulo: string;
}

export interface Pergunta {
  campo: string;
  texto: string;
  tipo: "faixa" | "opcao" | "numero" | "multipla";
  opcoes: Opcao[];
  padrao: Valor;
  ajuda: string | null;
  horizontal: boolean;
}

export interface Etapa {
  titulo: string;
  descricao: string;
  perguntas: Pergunta[];
}

export interface Questionario {
  etapas: Etapa[];
  padrao: Respostas;
  aviso: string;
}

export interface Classe {
  classe: string;
  nome: string;
  pct: number;
  por_mil: number;
  cor: string;
  o_que_e: string;
  papel: string;
  risco: string;
  resgate: string;
  motivo: string;
  minimo: number;
  maximo: number;
  afinidade: number;
}

export interface Produto {
  rotulo: string;
  classe_br: string;
  prob: number;
  fatores: { texto: string; direcao: "alta" | "baixa" }[];
}

export interface Resultado {
  avisos: string[];
  resumo: string[];
  perfil: {
    efetivo: string;
    pela_soma: string;
    pontos: number;
    pontos_max: number;
    limitado_por: string[];
    detalhamento: { pergunta: string; resposta: string; pontos: number }[];
  };
  risco: { nota: number; rotulo: string };
  segmento: { id: number; nome: string; descricao: string };
  saude: { modo_protecao: boolean; alertas: string[] };
  carteira: Classe[];
  proximos_passos: string[];
  produtos: Produto[];
  texto: string;
  aviso: string;
}
