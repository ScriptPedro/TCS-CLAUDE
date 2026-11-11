import { useEffect, useState, type FormEvent } from "react";
import { editarMeusDados, ErroApi, trocarSenha } from "../api";
import type { MeusDados, Regras, Sessao, Usuario } from "../types";
import { CampoIdade, CampoNome, CampoSenha, CampoTexto, ErrosGerais } from "./Campos";
import Icone from "./Icone";
import { rolarParaTopo } from "../rolagem";

interface Props {
  usuario: Usuario;
  regras: Regras | null;
  onAtualizado: (u: Usuario) => void;
  /** Trocar a senha encerra todas as sessões; o servidor devolve uma nova para este aparelho. */
  onNovaSessao: (s: Sessao) => void;
  onUsuarios: () => void;
  onSair: () => void;
}

type Tela = "resumo" | "dados" | "senha";

/** Separa os erros de campo (mostrados embaixo de cada campo) dos gerais (no topo). */
function separar(erro: unknown): [string[], Record<string, string>] {
  if (!(erro instanceof ErroApi)) return [["Erro inesperado. Tente novamente."], {}];
  const deCampo = new Set(Object.values(erro.campos));
  return [erro.erros.filter((m) => !deCampo.has(m)), erro.campos];
}

/** Aba "Conta": dados de quem entrou, edição, troca de senha, sair e, para admins, o gerenciamento. */
export default function Conta({ usuario, regras, onAtualizado, onNovaSessao, onUsuarios, onSair }: Props) {
  const [tela, setTela] = useState<Tela>("resumo");
  const [aviso, setAviso] = useState<string | null>(null);

  useEffect(() => {
    rolarParaTopo();
  }, [tela]);

  const concluir = (mensagem: string) => {
    setAviso(mensagem);
    setTela("resumo");
  };

  const titulo = tela === "dados" ? "Meus dados" : tela === "senha" ? "Trocar senha" : "Minha conta";

  return (
    <div className="tela-conta">
      <header className="barra-app">
        {tela === "resumo" ? <span className="botao-barra" aria-hidden /> : (
          <button className="botao-barra" onClick={() => setTela("resumo")} aria-label="Voltar"><Icone nome="voltar" /></button>
        )}
        <div className="barra-titulo">
          <span>{titulo}</span>
          <small>{usuario.papel === "admin" ? "Administrador" : "Cliente"}</small>
        </div>
        <span className="botao-barra" aria-hidden />
      </header>

      <main className="conteudo">
        {tela === "dados" && (
          <FormDados usuario={usuario} regras={regras} onCancelar={() => setTela("resumo")}
            onSalvo={(u) => { onAtualizado(u); concluir("Seus dados foram atualizados."); }} />
        )}
        {tela === "senha" && (
          <FormSenha regras={regras} onCancelar={() => setTela("resumo")}
            onSalvo={(s) => { onNovaSessao(s); concluir("Senha trocada. Os outros aparelhos precisam entrar de novo."); }} />
        )}
        {tela === "resumo" && (
          <>
            {aviso && <p className="sucesso" role="status">{aviso}</p>}
            <section className="cartao-bloco">
              <p className="bloco-titulo">{usuario.nome}</p>
              <dl className="ficha">
                <div><dt>E-mail</dt><dd>{usuario.email}</dd></div>
                <div><dt>CPF</dt><dd>{usuario.cpf}</dd></div>
                <div><dt>Idade</dt><dd>{usuario.idade} anos</dd></div>
              </dl>
            </section>

            <section className="cartao-bloco menu-conta">
              <button className="bloco-cabeca" onClick={() => { setAviso(null); setTela("dados"); }}>
                <span><Icone nome="usuario" /> Editar meus dados</span>
                <Icone nome="seta" />
              </button>
              <button className="bloco-cabeca" onClick={() => { setAviso(null); setTela("senha"); }}>
                <span><Icone nome="cadeado" /> Trocar senha</span>
                <Icone nome="seta" />
              </button>
              {usuario.papel === "admin" && (
                <button className="bloco-cabeca" onClick={onUsuarios}>
                  <span><Icone nome="pessoas" /> Gerenciar usuários</span>
                  <Icone nome="seta" />
                </button>
              )}
            </section>

            <button className="botao grande sair" onClick={onSair}>Sair da conta</button>
          </>
        )}
      </main>
    </div>
  );
}

function FormDados({ usuario, regras, onSalvo, onCancelar }: {
  usuario: Usuario; regras: Regras | null; onSalvo: (u: Usuario) => void; onCancelar: () => void;
}) {
  const [dados, setDados] = useState<MeusDados>({ nome: usuario.nome, email: usuario.email, idade: String(usuario.idade) });
  const [erros, setErros] = useState<string[]>([]);
  const [campos, setCampos] = useState<Record<string, string>>({});
  const [enviando, setEnviando] = useState(false);

  const mudar = (campo: keyof MeusDados) => (v: string) => {
    setDados({ ...dados, [campo]: v });
    if (campos[campo]) setCampos({ ...campos, [campo]: "" });
  };

  const enviar = async (e: FormEvent) => {
    e.preventDefault();
    setEnviando(true);
    setErros([]);
    setCampos({});
    try {
      onSalvo(await editarMeusDados(dados));
    } catch (erro) {
      const [gerais, porCampo] = separar(erro);
      setErros(gerais);
      setCampos(porCampo);
    } finally {
      setEnviando(false);
    }
  };

  return (
    <form className="formulario" onSubmit={enviar} noValidate>
      <ErrosGerais erros={erros} />
      <CampoNome rotulo="Nome completo" valor={dados.nome} erro={campos.nome} onChange={mudar("nome")} regras={regras} />
      <div className="campo">
        <span className="campo-rotulo">CPF</span>
        <p className="campo-fixo">{usuario.cpf}</p>
        <p className="campo-ajuda">O CPF identifica você e não muda depois do cadastro.</p>
      </div>
      <CampoTexto rotulo="E-mail" tipo="email" inputMode="email" autoComplete="email" valor={dados.email}
        erro={campos.email} onChange={mudar("email")} />
      <CampoIdade rotulo="Idade" valor={dados.idade} erro={campos.idade} onChange={mudar("idade")} regras={regras} />
      <div className="card-acoes">
        <button type="button" className="botao" onClick={onCancelar}>Cancelar</button>
        <button className="botao primario" disabled={enviando}>{enviando ? "Salvando…" : "Salvar"}</button>
      </div>
    </form>
  );
}

function FormSenha({ regras, onSalvo, onCancelar }: { regras: Regras | null; onSalvo: (s: Sessao) => void; onCancelar: () => void }) {
  const [atual, setAtual] = useState("");
  const [nova, setNova] = useState("");
  const [confirmar, setConfirmar] = useState("");
  const [erros, setErros] = useState<string[]>([]);
  const [campos, setCampos] = useState<Record<string, string>>({});
  const [enviando, setEnviando] = useState(false);

  const enviar = async (e: FormEvent) => {
    e.preventDefault();
    setErros([]);
    setCampos({});
    if (nova !== confirmar) {
      setCampos({ confirmar: "As senhas não são iguais." });
      return;
    }
    setEnviando(true);
    try {
      onSalvo(await trocarSenha(atual, nova));
    } catch (erro) {
      const [gerais, porCampo] = separar(erro);
      setErros(gerais);
      setCampos(porCampo);
    } finally {
      setEnviando(false);
    }
  };

  return (
    <form className="formulario" onSubmit={enviar} noValidate>
      <ErrosGerais erros={erros} />
      <CampoSenha rotulo="Senha atual" valor={atual} erro={campos.senha_atual} onChange={setAtual} novaSenha={false} />
      <CampoSenha rotulo="Nova senha" valor={nova} erro={campos.nova_senha} onChange={setNova}
        ajuda={`Pelo menos ${regras?.senha_min ?? 8} caracteres, com letras e números.`} />
      <CampoSenha rotulo="Repita a nova senha" valor={confirmar} erro={campos.confirmar} onChange={setConfirmar} />
      <p className="campo-ajuda">Ao trocar a senha, os outros aparelhos em que você entrou saem da conta.</p>
      <div className="card-acoes">
        <button type="button" className="botao" onClick={onCancelar}>Cancelar</button>
        <button className="botao primario" disabled={enviando}>{enviando ? "Trocando…" : "Trocar senha"}</button>
      </div>
    </form>
  );
}
