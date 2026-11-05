import type { Respostas, Resultado } from "./types";

// Respostas e último resultado ficam no aparelho para sobreviver a um recarregamento (conveniência, não dado oficial)
const CHAVE_RESPOSTAS = "assessor.respostas";
const CHAVE_RESULTADO = "assessor.resultado";

function ler<T>(chave: string): T | null {
  try {
    return JSON.parse(localStorage.getItem(chave) ?? "null");
  } catch {
    return null;
  }
}
function gravar(chave: string, valor: unknown) {
  try {
    if (valor) localStorage.setItem(chave, JSON.stringify(valor));
    else localStorage.removeItem(chave);
  } catch {
    /* armazenamento indisponível: segue sem salvar */
  }
}

export const lerRespostas = () => ler<Respostas>(CHAVE_RESPOSTAS);
export const salvarRespostas = (r: Respostas | null) => gravar(CHAVE_RESPOSTAS, r);
export const lerResultado = () => ler<Resultado>(CHAVE_RESULTADO);
export const salvarResultado = (r: Resultado | null) => gravar(CHAVE_RESULTADO, r);
