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
  /** Brasileiros da mesma renda e idade (Raio X ANBIMA, D36); null sem a tabela. */
  referencia_br: ReferenciaBR | null;
  calculo: { passos: string[]; rotulo_afinidade: string };
  produtos: Produto[];
  texto: string;
  aviso: string;
}

export interface ReferenciaBR {
  faixa_renda: string;
  faixa_idade: string;
  entrevistados: number;
  algum_investimento: number;
  posse: { classe: string; nome: string; fracao: number }[];
  fonte: string;
  /** Frases prontas (podem ter **negrito**): o que o grupo faz × o que o perfil pede. */
  linhas: string[];
}

// Usuários (api/usuarios.py, D40)
export type Papel = "usuario" | "admin";

export interface Usuario {
  id: number;
  nome: string;
  /** Completo (000.000.000-00) para o próprio usuário e na ficha; mascarado (***.000.000-**) na lista. */
  cpf: string;
  email: string;
  idade: number;
  papel: Papel;
  criado_em: string;
  atualizado_em: string;
  excluido_em: string | null;
}

/** Limites dos campos, vindos do servidor (src/config.py) para não duplicar regra aqui. */
export interface Regras {
  idade_minima: number;
  idade_maxima: number;
  nome_max: number;
  senha_min: number;
  senha_max: number;
  papeis: Papel[];
}

export interface Sessao {
  token: string;
  usuario: Usuario;
}

export interface DadosUsuario {
  nome: string;
  cpf?: string;
  email: string;
  idade: string;
  senha: string;
  papel?: Papel;
}
