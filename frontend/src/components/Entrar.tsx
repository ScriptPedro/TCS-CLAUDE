import { useState, type FormEvent } from "react";
import { entrar, ErroApi, registrar } from "../api";
import type { DadosUsuario, Regras, Sessao } from "../types";
import { CampoCpf, CampoIdade, CampoNome, CampoSenha, CampoTexto, ErrosGerais } from "./Campos";

interface Props {
  regras: Regras | null;
  onEntrou: (s: Sessao) => void;
}

type Modo = "login" | "registro";

const VAZIO: DadosUsuario & { confirmar: string } = { nome: "", cpf: "", email: "", idade: "", senha: "", confirmar: "" };

/** Primeira tela do app: entrar com e-mail ou CPF, ou criar uma conta. */
export default function Entrar({ regras, onEntrou }: Props) {
  const [modo, setModo] = useState<Modo>("login");
  const [login, setLogin] = useState("");
  const [senha, setSenha] = useState("");
  const [dados, setDados] = useState(VAZIO);
  const [erros, setErros] = useState<string[]>([]);
  const [campos, setCampos] = useState<Record<string, string>>({});
  const [enviando, setEnviando] = useState(false);

  const trocar = (m: Modo) => {
    setModo(m);
    setErros([]);
    setCampos({});
  };

  const mudar = (campo: keyof typeof VAZIO) => (v: string) => {
    setDados({ ...dados, [campo]: v });
    if (campos[campo]) setCampos({ ...campos, [campo]: "" });
  };

  const enviar = async (e: FormEvent) => {
    e.preventDefault();
    setErros([]);
    setCampos({});
    if (modo === "registro" && dados.senha !== dados.confirmar) {
      setCampos({ confirmar: "As senhas não são iguais." });
      return;
    }
    setEnviando(true);
    try {
      const { confirmar: _, ...corpo } = dados;
      onEntrou(modo === "login" ? await entrar(login, senha) : await registrar(corpo));
    } catch (erro) {
      if (erro instanceof ErroApi) {
        setCampos(erro.campos);
        // Os erros de campo aparecem embaixo de cada campo; os demais ficam no topo
        const deCampo = new Set(Object.values(erro.campos));
        setErros(erro.erros.filter((m) => !deCampo.has(m)));
      } else setErros(["Erro inesperado. Tente novamente."]);
    } finally {
      setEnviando(false);
    }
  };

  return (
    <div className="tela-entrar">
      <header className="entrar-topo">
        <span className="avatar" aria-hidden>C</span>
        <p className="banco-ola">Banco Cédula</p>
        <p className="banco-agencia">Seu banco com assessor de investimentos virtual</p>
      </header>

      <main className="conteudo">
        <div className="abas" role="tablist" aria-label="Acesso">
          <button role="tab" aria-selected={modo === "login"} className={modo === "login" ? "ativa" : ""} onClick={() => trocar("login")}>
            Entrar
          </button>
          <button role="tab" aria-selected={modo === "registro"} className={modo === "registro" ? "ativa" : ""} onClick={() => trocar("registro")}>
            Criar conta
          </button>
        </div>

        <form className="formulario" onSubmit={enviar} noValidate>
          <ErrosGerais erros={erros} />
          {modo === "login" ? (
            <>
              <CampoTexto rotulo="E-mail ou CPF" valor={login} onChange={setLogin} autoComplete="username" />
              <CampoSenha rotulo="Senha" valor={senha} onChange={setSenha} novaSenha={false} />
              <button className="botao primario grande" disabled={enviando}>{enviando ? "Entrando…" : "Entrar"}</button>
            </>
          ) : (
            <>
              <CampoNome rotulo="Nome completo" valor={dados.nome} erro={campos.nome} onChange={mudar("nome")} regras={regras} />
              <CampoCpf rotulo="CPF" valor={dados.cpf ?? ""} erro={campos.cpf} onChange={mudar("cpf")} />
              <CampoTexto
                rotulo="E-mail" tipo="email" inputMode="email" autoComplete="email" valor={dados.email}
                erro={campos.email} onChange={mudar("email")}
              />
              <CampoIdade rotulo="Idade" valor={dados.idade} erro={campos.idade} onChange={mudar("idade")} regras={regras} />
              <CampoSenha
                rotulo="Senha" valor={dados.senha} erro={campos.senha} onChange={mudar("senha")}
                ajuda={`Pelo menos ${regras?.senha_min ?? 8} caracteres, com letras e números.`}
              />
              <CampoSenha rotulo="Repita a senha" valor={dados.confirmar} erro={campos.confirmar} onChange={mudar("confirmar")} />
              <button className="botao primario grande" disabled={enviando}>{enviando ? "Criando…" : "Criar conta"}</button>
            </>
          )}
        </form>

        <p className="suave pequeno centro">Banco Cédula é um banco fictício, criado para demonstrar o projeto.</p>
      </main>
    </div>
  );
}
