import { useId, useState, type ReactNode } from "react";
import type { Regras } from "../types";

// Campos dos formulários de usuário. Aqui só se filtra o que pode ser digitado;
// a validação de verdade (dígitos do CPF, nome e sobrenome, limites) é a do servidor (api/validacao.py).

interface Base {
  rotulo: string;
  valor: string;
  erro?: string;
  ajuda?: ReactNode;
  onChange: (v: string) => void;
}

function Moldura({ id, rotulo, erro, ajuda, children }: { id: string; rotulo: string; erro?: string; ajuda?: ReactNode; children: ReactNode }) {
  return (
    <div className={`campo ${erro ? "com-erro" : ""}`}>
      <label htmlFor={id}>{rotulo}</label>
      {children}
      {erro ? <p className="campo-erro" id={`${id}-erro`} role="alert">{erro}</p> : ajuda && <p className="campo-ajuda" id={`${id}-ajuda`}>{ajuda}</p>}
    </div>
  );
}

function descricao(id: string, erro?: string, ajuda?: ReactNode) {
  return erro ? `${id}-erro` : ajuda ? `${id}-ajuda` : undefined;
}

export function CampoTexto({ rotulo, valor, erro, ajuda, onChange, tipo = "text", autoComplete, maxLength, filtro, inputMode }: Base & {
  tipo?: string;
  autoComplete?: string;
  maxLength?: number;
  filtro?: (v: string) => string;
  inputMode?: "text" | "numeric" | "email";
}) {
  const id = useId();
  return (
    <Moldura id={id} rotulo={rotulo} erro={erro} ajuda={ajuda}>
      <input
        id={id} type={tipo} value={valor} autoComplete={autoComplete} maxLength={maxLength} inputMode={inputMode}
        aria-invalid={Boolean(erro)} aria-describedby={descricao(id, erro, ajuda)}
        onChange={(e) => onChange(filtro ? filtro(e.target.value) : e.target.value)}
      />
    </Moldura>
  );
}

/** Letras (com acento), espaço, apóstrofo e hífen; números e símbolos nem entram. */
export const filtrarNome = (v: string) => v.replace(/[^\p{L} '\-]/gu, "").replace(/^\s+/, "");

export function CampoNome(props: Base & { regras: Regras | null }) {
  return (
    <CampoTexto
      {...props} autoComplete="name" maxLength={props.regras?.nome_max} filtro={filtrarNome}
      ajuda={props.ajuda ?? "Nome e sobrenome, só com letras."}
    />
  );
}

/** Só dígitos, no máximo 11, exibidos com a máscara 000.000.000-00. */
export function mascararCpf(v: string) {
  const d = v.replace(/\D/g, "").slice(0, 11);
  return d
    .replace(/^(\d{3})(\d)/, "$1.$2")
    .replace(/^(\d{3})\.(\d{3})(\d)/, "$1.$2.$3")
    .replace(/\.(\d{3})(\d{1,2})$/, ".$1-$2");
}

export function CampoCpf(props: Base) {
  return <CampoTexto {...props} inputMode="numeric" autoComplete="off" maxLength={14} filtro={mascararCpf} />;
}

/**
 * Idade: só algarismos. Sinal, ponto, vírgula, "e" e zero à esquerda não entram, e um valor acima
 * do maior registro de idade da história (vindo do servidor) é ignorado em vez de aceito.
 */
export function filtrarIdade(novo: string, anterior: string, maxima: number) {
  const d = novo.replace(/\D/g, "").replace(/^0+/, "");
  if (d === "") return "";
  return Number(d) > maxima ? anterior : d;
}

export function CampoIdade({ regras, ...props }: Base & { regras: Regras | null }) {
  const maxima = regras?.idade_maxima ?? 122;
  return (
    <CampoTexto
      {...props} inputMode="numeric" autoComplete="off" maxLength={String(maxima).length}
      filtro={(v) => filtrarIdade(v, props.valor, maxima)}
      ajuda={props.ajuda ?? `Em anos, de ${regras?.idade_minima ?? 1} a ${maxima} (o maior registro de idade da história).`}
    />
  );
}

export function CampoSenha({ novaSenha = true, ...props }: Base & { novaSenha?: boolean }) {
  const id = useId();
  const [visivel, setVisivel] = useState(false);
  return (
    <Moldura id={id} rotulo={props.rotulo} erro={props.erro} ajuda={props.ajuda}>
      <div className="campo-senha">
        <input
          id={id} type={visivel ? "text" : "password"} value={props.valor}
          autoComplete={novaSenha ? "new-password" : "current-password"}
          aria-invalid={Boolean(props.erro)} aria-describedby={descricao(id, props.erro, props.ajuda)}
          onChange={(e) => props.onChange(e.target.value)}
        />
        <button type="button" className="link" onClick={() => setVisivel(!visivel)} aria-pressed={visivel}>
          {visivel ? "Ocultar" : "Mostrar"}
        </button>
      </div>
    </Moldura>
  );
}

export function ErrosGerais({ erros }: { erros: string[] }) {
  if (!erros.length) return null;
  return (
    <div className="erro" role="alert">
      {erros.map((e) => <p key={e}>{e}</p>)}
    </div>
  );
}
