import type { Usuario } from "../types";
import Icone from "./Icone";

interface Props {
  usuario: Usuario;
  onUsuarios: () => void;
  onSair: () => void;
}

/** Aba "Conta": dados de quem entrou, sair e, para administradores, o gerenciamento de usuários. */
export default function Conta({ usuario, onUsuarios, onSair }: Props) {
  return (
    <div className="tela-conta">
      <header className="barra-app">
        <span className="botao-barra" aria-hidden />
        <div className="barra-titulo">
          <span>Minha conta</span>
          <small>{usuario.papel === "admin" ? "Administrador" : "Cliente"}</small>
        </div>
        <span className="botao-barra" aria-hidden />
      </header>

      <main className="conteudo">
        <section className="cartao-bloco">
          <p className="bloco-titulo">{usuario.nome}</p>
          <dl className="ficha">
            <div><dt>E-mail</dt><dd>{usuario.email}</dd></div>
            <div><dt>CPF</dt><dd>{usuario.cpf}</dd></div>
            <div><dt>Idade</dt><dd>{usuario.idade} anos</dd></div>
          </dl>
        </section>

        {usuario.papel === "admin" && (
          <section className="cartao-bloco">
            <button className="bloco-cabeca" onClick={onUsuarios}>
              <span><Icone nome="pessoas" /> Gerenciar usuários</span>
              <Icone nome="seta" />
            </button>
            <p className="suave pequeno">Cadastrar, editar, excluir e restaurar contas.</p>
          </section>
        )}

        <button className="botao grande sair" onClick={onSair}>Sair da conta</button>
      </main>
    </div>
  );
}
