import { lerToken } from "./armazenamento";
import type { DadosUsuario, Questionario, Regras, Respostas, Resultado, Sessao, Usuario } from "./types";

export class ErroApi extends Error {
  constructor(
    public erros: string[],
    /** Mensagem de cada campo do formulário que o servidor recusou. */
    public campos: Record<string, string> = {},
    public status = 0,
  ) {
    super(erros.join(" "));
  }
}

// Chamado quando o servidor diz que a sessão não vale mais (401): o App volta para o login
let aoExpirar: () => void = () => {};
export const quandoSessaoExpirar = (f: () => void) => {
  aoExpirar = f;
};

async function ler<T>(resp: Response): Promise<T> {
  const corpo = resp.status === 204 ? null : await resp.json().catch(() => null);
  if (!resp.ok) {
    const erros = corpo?.detail?.erros ?? [`Erro ${resp.status} ao falar com o servidor.`];
    throw new ErroApi(erros, corpo?.detail?.campos ?? {}, resp.status);
  }
  return corpo as T;
}

async function chamar<T>(rota: string, metodo = "GET", corpo?: unknown, autenticado = true): Promise<T> {
  const headers: Record<string, string> = {};
  if (corpo !== undefined) headers["Content-Type"] = "application/json";
  const token = lerToken();
  if (autenticado && token) headers.Authorization = `Bearer ${token}`;
  let resp: Response;
  try {
    resp = await fetch(rota, { method: metodo, headers, body: corpo === undefined ? undefined : JSON.stringify(corpo) });
  } catch {
    throw new ErroApi(["Não foi possível conectar à API. Ela está rodando em http://localhost:8000?"]);
  }
  try {
    return await ler<T>(resp);
  } catch (e) {
    if (e instanceof ErroApi && e.status === 401 && autenticado && token) aoExpirar();
    throw e;
  }
}

export async function buscarQuestionario(): Promise<Questionario> {
  return chamar<Questionario>("/api/questionario", "GET", undefined, false);
}

export async function pedirRecomendacao(respostas: Respostas): Promise<Resultado> {
  return chamar<Resultado>("/api/recomendacao", "POST", { respostas }, false);
}

// --- Usuários --------------------------------------------------------------
export const buscarRegras = () => chamar<Regras>("/api/auth/regras", "GET", undefined, false);
export const entrar = (login: string, senha: string) => chamar<Sessao>("/api/auth/login", "POST", { login, senha }, false);
export const registrar = (dados: DadosUsuario) => chamar<Sessao>("/api/auth/registro", "POST", dados, false);
export const sair = () => chamar<null>("/api/auth/logout", "POST");
export const quemSouEu = () => chamar<Usuario>("/api/auth/eu");

export const listarUsuarios = (busca: string, excluidos: boolean) =>
  chamar<Usuario[]>(`/api/usuarios?${new URLSearchParams({ busca, excluidos: String(excluidos) })}`);
export const criarUsuario = (dados: DadosUsuario) => chamar<Usuario>("/api/usuarios", "POST", dados);
export const buscarUsuario = (id: number) => chamar<Usuario>(`/api/usuarios/${id}`);
export const editarUsuario = (id: number, dados: DadosUsuario) => chamar<Usuario>(`/api/usuarios/${id}`, "PUT", dados);
export const excluirUsuario = (id: number) => chamar<null>(`/api/usuarios/${id}`, "DELETE");
export const restaurarUsuario = (id: number) => chamar<Usuario>(`/api/usuarios/${id}/restaurar`, "POST");
