import { useCallback, useEffect, useState, type FormEvent } from "react";
import {
  apagarDefinitivo, buscarUsuario, criarUsuario, editarUsuario, ErroApi, excluirUsuario, listarUsuarios, restaurarUsuario,
} from "../api";
import type { DadosUsuario, Papel, Regras, Usuario } from "../types";
import { CampoCpf, CampoIdade, CampoNome, CampoSenha, CampoTexto, ErrosGerais } from "./Campos";
import Icone from "./Icone";

interface Props {
  eu: Usuario;
  regras: Regras | null;
  onSair: () => void;
}

const ROTULO_PAPEL: Record<Papel, string> = { usuario: "Usuário", admin: "Administrador" };

const data = (iso: string) => new Date(iso).toLocaleDateString("pt-BR");

/** Gerenciamento de usuários: só administradores chegam aqui (o servidor também confere). */
export default function Usuarios({ eu, regras, onSair }: Props) {
  const [lista, setLista] = useState<Usuario[] | null>(null);
  const [busca, setBusca] = useState("");
  const [excluidos, setExcluidos] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  const [editando, setEditando] = useState<Usuario | "novo" | null>(null);
  const [confirmando, setConfirmando] = useState<number | null>(null);
  const [apagando, setApagando] = useState<number | null>(null);

  const carregar = useCallback(async () => {
    try {
      setLista(await listarUsuarios(busca, excluidos));
      setErro(null);
    } catch (e) {
      setErro(e instanceof ErroApi ? e.message : "Erro ao carregar os usuários.");
    }
  }, [busca, excluidos]);

  useEffect(() => {
    const t = window.setTimeout(carregar, 250); // espera a pessoa parar de digitar a busca
    return () => window.clearTimeout(t);
  }, [carregar]);

  const acao = async (f: () => Promise<unknown>, mensagem: string) => {
    try {
      await f();
      setAviso(mensagem);
      setConfirmando(null);
      setApagando(null);
      await carregar();
    } catch (e) {
      setErro(e instanceof ErroApi ? e.message : "Não foi possível concluir a ação.");
    }
  };

  const abrirEdicao = async (u: Usuario) => {
    try {
      setEditando(await buscarUsuario(u.id)); // a ficha traz o CPF completo; a lista, mascarado
    } catch (e) {
      setErro(e instanceof ErroApi ? e.message : "Não foi possível abrir o usuário.");
    }
  };

  const salvo = async (mensagem: string) => {
    setEditando(null);
    setAviso(mensagem);
    await carregar();
  };

  useEffect(() => {
    window.scrollTo({ top: 0 });
  }, [editando]);

  return (
    <div className="tela-usuarios">
      <header className="barra-app">
        <button className="botao-barra" onClick={editando ? () => setEditando(null) : onSair} aria-label="Voltar">
          <Icone nome="voltar" />
        </button>
        <div className="barra-titulo">
          <span>{editando === "novo" ? "Novo usuário" : editando ? "Editar usuário" : "Usuários"}</span>
          <small>Administração</small>
        </div>
        <span className="botao-barra" aria-hidden />
      </header>

      <main className="conteudo">
        {editando ? (
          <FormUsuario usuario={editando === "novo" ? null : editando} eu={eu} regras={regras}
            onSalvo={salvo} onCancelar={() => setEditando(null)} />
        ) : (
          <>
            {aviso && <p className="sucesso" role="status">{aviso}</p>}
            {erro && <ErrosGerais erros={[erro]} />}

            <div className="filtros">
              <CampoTexto rotulo="Buscar por nome, e-mail ou CPF" valor={busca} onChange={setBusca} tipo="search" />
              <label className="marcar">
                <input type="checkbox" checked={excluidos} onChange={(e) => setExcluidos(e.target.checked)} />
                Mostrar excluídos
              </label>
              <button className="botao primario" onClick={() => { setAviso(null); setEditando("novo"); }}>Novo usuário</button>
            </div>

            {lista === null && !erro && <p className="carregando">Carregando…</p>}
            {lista?.length === 0 && <p className="suave">Nenhum usuário encontrado.</p>}
            <ul className="lista-usuarios">
              {lista?.map((u) => (
                <li key={u.id} className={`cartao-bloco ${u.excluido_em ? "excluido" : ""}`}>
                  <div className="usuario-cabeca">
                    <strong>{u.nome}</strong>
                    <span className="selos">
                      {u.papel === "admin" && <span className="selo">Admin</span>}
                      {u.id === eu.id && <span className="selo claro">Você</span>}
                      {u.excluido_em && <span className="selo alerta">Excluído em {data(u.excluido_em)}</span>}
                    </span>
                  </div>
                  <p className="suave pequeno">{u.email} · CPF {u.cpf} · {u.idade} anos</p>
                  <div className="usuario-acoes">
                    {u.excluido_em && apagando === u.id ? (
                      <div className="confirmar-apagar">
                        <p className="pequeno">
                          <strong>Apagar de vez a conta de {u.nome}?</strong> Os dados e as recomendações dessa pessoa
                          saem do banco e não dá para desfazer. Use para pedidos de eliminação da LGPD.
                        </p>
                        <button className="botao perigo" onClick={() => acao(() => apagarDefinitivo(u.id), `A conta de ${u.nome} foi apagada definitivamente.`)}>
                          Apagar de vez
                        </button>
                        <button className="botao" onClick={() => setApagando(null)}>Cancelar</button>
                      </div>
                    ) : u.excluido_em ? (
                      <>
                        <button className="botao" onClick={() => acao(() => restaurarUsuario(u.id), `A conta de ${u.nome} foi restaurada.`)}>
                          Restaurar
                        </button>
                        <button className="botao" onClick={() => setApagando(u.id)}>Apagar definitivamente</button>
                      </>
                    ) : confirmando === u.id ? (
                      <>
                        <span className="pequeno">Excluir a conta de {u.nome.split(" ")[0]}?</span>
                        <button className="botao perigo" onClick={() => acao(() => excluirUsuario(u.id), `A conta de ${u.nome} foi excluída. Dá para restaurá-la em "Mostrar excluídos".`)}>
                          Sim, excluir
                        </button>
                        <button className="botao" onClick={() => setConfirmando(null)}>Cancelar</button>
                      </>
                    ) : (
                      <>
                        <button className="botao" onClick={() => abrirEdicao(u)}>Editar</button>
                        {u.id !== eu.id && <button className="botao" onClick={() => setConfirmando(u.id)}>Excluir</button>}
                      </>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          </>
        )}
      </main>
    </div>
  );
}

interface FormProps {
  usuario: Usuario | null;
  eu: Usuario;
  regras: Regras | null;
  onSalvo: (mensagem: string) => void;
  onCancelar: () => void;
}

function FormUsuario({ usuario, eu, regras, onSalvo, onCancelar }: FormProps) {
  const novo = usuario === null;
  const [dados, setDados] = useState<DadosUsuario>({
    nome: usuario?.nome ?? "",
    cpf: "",
    email: usuario?.email ?? "",
    idade: usuario ? String(usuario.idade) : "",
    senha: "",
    papel: usuario?.papel ?? "usuario",
  });
  const [erros, setErros] = useState<string[]>([]);
  const [campos, setCampos] = useState<Record<string, string>>({});
  const [enviando, setEnviando] = useState(false);
  const souEu = usuario?.id === eu.id;

  const mudar = (campo: keyof DadosUsuario) => (v: string) => {
    setDados({ ...dados, [campo]: v });
    if (campos[campo]) setCampos({ ...campos, [campo]: "" });
  };

  const enviar = async (e: FormEvent) => {
    e.preventDefault();
    setEnviando(true);
    setErros([]);
    setCampos({});
    try {
      if (novo) {
        const u = await criarUsuario(dados);
        onSalvo(`A conta de ${u.nome} foi cadastrada.`);
      } else {
        const { cpf: _, ...corpo } = dados; // CPF não muda depois do cadastro
        const u = await editarUsuario(usuario.id, corpo);
        onSalvo(`A conta de ${u.nome} foi atualizada.`);
      }
    } catch (erro) {
      if (erro instanceof ErroApi) {
        setCampos(erro.campos);
        const deCampo = new Set(Object.values(erro.campos));
        setErros(erro.erros.filter((m) => !deCampo.has(m)));
      } else setErros(["Erro inesperado. Tente novamente."]);
    } finally {
      setEnviando(false);
    }
  };

  return (
    <form className="formulario" onSubmit={enviar} noValidate>
      <ErrosGerais erros={erros} />
      <CampoNome rotulo="Nome completo" valor={dados.nome} erro={campos.nome} onChange={mudar("nome")} regras={regras} />
      {novo ? (
        <CampoCpf rotulo="CPF" valor={dados.cpf ?? ""} erro={campos.cpf} onChange={mudar("cpf")} />
      ) : (
        <div className="campo">
          <span className="campo-rotulo">CPF</span>
          <p className="campo-fixo">{usuario.cpf}</p>
          <p className="campo-ajuda">O CPF identifica a pessoa e não muda depois do cadastro.</p>
        </div>
      )}
      <CampoTexto rotulo="E-mail" tipo="email" inputMode="email" valor={dados.email} erro={campos.email} onChange={mudar("email")} />
      <CampoIdade rotulo="Idade" valor={dados.idade} erro={campos.idade} onChange={mudar("idade")} regras={regras} />

      <fieldset className="campo">
        <legend className="campo-rotulo">Tipo de usuário</legend>
        <div className="opcoes horizontal" role="radiogroup">
          {(regras?.papeis ?? ["usuario", "admin"]).map((p) => (
            <label key={p} className={`opcao ${dados.papel === p ? "marcada" : ""}`}>
              <input type="radio" name="papel" value={p} checked={dados.papel === p} disabled={souEu && p !== "admin"}
                onChange={() => mudar("papel")(p)} />
              <span className="radio" aria-hidden />
              <span>{ROTULO_PAPEL[p]}</span>
            </label>
          ))}
        </div>
        {campos.papel ? <p className="campo-erro" role="alert">{campos.papel}</p>
          : souEu && <p className="campo-ajuda">Você não pode tirar o seu próprio acesso de administrador.</p>}
      </fieldset>

      <CampoSenha
        rotulo={novo ? "Senha" : "Nova senha (opcional)"} valor={dados.senha} erro={campos.senha} onChange={mudar("senha")}
        ajuda={novo ? `Pelo menos ${regras?.senha_min ?? 8} caracteres, com letras e números.`
          : "Deixe em branco para manter a senha atual. Trocar a senha encerra os logins abertos da pessoa."}
      />

      <div className="card-acoes">
        <button type="button" className="botao" onClick={onCancelar}>Cancelar</button>
        <button className="botao primario" disabled={enviando}>{enviando ? "Salvando…" : novo ? "Cadastrar" : "Salvar"}</button>
      </div>
    </form>
  );
}
