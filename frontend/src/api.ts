import type { Questionario, Respostas, Resultado } from "./types";

export class ErroApi extends Error {
  constructor(public erros: string[]) {
    super(erros.join(" "));
  }
}

async function ler<T>(resp: Response): Promise<T> {
  const corpo = await resp.json().catch(() => null);
  if (!resp.ok) {
    const erros = corpo?.detail?.erros ?? [`Erro ${resp.status} ao falar com o servidor.`];
    throw new ErroApi(erros);
  }
  return corpo as T;
}

export async function buscarQuestionario(): Promise<Questionario> {
  try {
    return await ler<Questionario>(await fetch("/api/questionario"));
  } catch (e) {
    if (e instanceof ErroApi) throw e;
    throw new ErroApi(["Não foi possível conectar à API. Ela está rodando em http://localhost:8000?"]);
  }
}

export async function pedirRecomendacao(respostas: Respostas): Promise<Resultado> {
  const resp = await fetch("/api/recomendacao", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ respostas }),
  });
  return ler<Resultado>(resp);
}
