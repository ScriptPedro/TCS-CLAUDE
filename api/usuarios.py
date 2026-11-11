"""Rotas de usuários (D40): cadastro, login e gerenciamento (só administradores).

    GET    /api/auth/regras               → limites dos campos (o front usa para filtrar a digitação)
    POST   /api/auth/registro             → cria conta comum e já entra
    POST   /api/auth/login                → e-mail ou CPF + senha → token (bloqueia após várias senhas erradas)
    POST   /api/auth/logout               → encerra a sessão do token
    GET    /api/auth/eu                   → usuário do token
    PUT    /api/auth/eu                   → a pessoa edita o próprio nome, e-mail e idade
    POST   /api/auth/senha                → a pessoa troca a própria senha (senha atual + nova)

    GET    /api/usuarios?busca=&excluidos= → lista (admin)
    POST   /api/usuarios                   → cria, podendo escolher o tipo (admin)
    GET    /api/usuarios/{id}              → um usuário, inclusive excluído (admin)
    PUT    /api/usuarios/{id}              → edita nome, e-mail, idade, tipo e/ou senha (admin)
    DELETE /api/usuarios/{id}              → soft delete (admin)
    POST   /api/usuarios/{id}/restaurar    → desfaz o soft delete (admin)
    DELETE /api/usuarios/{id}/definitivo   → apaga de vez quem já está excluído, com recomendações (admin, LGPD)

O token vai no cabeçalho ``Authorization: Bearer <token>``. Erros seguem o formato do
resto da API: ``{"detail": {"erros": [...], "campos": {campo: mensagem}}}``.

Primeiro administrador (na raiz do projeto):
    python -m api.usuarios criar-admin
"""

from __future__ import annotations

import argparse
import getpass
import sys
from collections.abc import Iterator
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from pydantic import BaseModel

from api import banco
from api.validacao import formatar_cpf, mascarar_cpf, validar
from src import config

roteador = APIRouter(prefix="/api")

CAMPOS_REGISTRO = ["nome", "cpf", "email", "idade", "senha"]


def _erro(codigo: int, mensagem: str, campos: dict[str, str] | None = None) -> HTTPException:
    return HTTPException(status_code=codigo, detail={"erros": [mensagem], "campos": campos or {}})


def _erro_validacao(campos: dict[str, str]) -> HTTPException:
    return HTTPException(status_code=422, detail={"erros": list(campos.values()), "campos": campos})


def _conflito(exc: banco.Conflito) -> HTTPException:
    return _erro(409, exc.mensagem, {exc.campo: exc.mensagem})


def serializar(u: dict[str, Any], cpf_completo: bool = False) -> dict[str, Any]:
    """Usuário em JSON. O CPF sai mascarado, exceto para o próprio dono ou na ficha do admin."""
    return {
        "id": u["id"],
        "nome": u["nome"],
        "cpf": formatar_cpf(u["cpf"]) if cpf_completo else mascarar_cpf(u["cpf"]),
        "email": u["email"],
        "idade": u["idade"],
        "papel": u["papel"],
        "criado_em": u["criado_em"],
        "atualizado_em": u["atualizado_em"],
        "excluido_em": u["excluido_em"],
    }


# ---------------------------------------------------------------------------
# Dependências
# ---------------------------------------------------------------------------
def conexao() -> Iterator[banco.Conexao]:
    """Uma conexão por requisição (um Postgres de projeto acadêmico não precisa de pool)."""
    with banco.conectar() as con:
        yield con


def _token(authorization: str | None) -> str:
    esquema, _, token = (authorization or "").partition(" ")
    if esquema.lower() != "bearer" or not token.strip():
        raise _erro(401, "Faça login para continuar.")
    return token.strip()


def token_obrigatorio(authorization: str | None = Header(default=None)) -> str:
    return _token(authorization)


def usuario_logado(
    token: str = Depends(token_obrigatorio),  # antes da conexão: sem token, 401 sem nem abrir o banco
    con: banco.Conexao = Depends(conexao),
) -> dict[str, Any]:
    usuario = banco.usuario_da_sessao(con, token)
    if usuario is None:
        raise _erro(401, "Sua sessão expirou. Entre de novo.")
    return usuario


def exigir_admin(usuario: dict[str, Any] = Depends(usuario_logado)) -> dict[str, Any]:
    if usuario["papel"] != "admin":
        raise _erro(403, "Apenas administradores podem gerenciar usuários.")
    return usuario


# ---------------------------------------------------------------------------
# Corpos das requisições. Os campos aceitam qualquer tipo de propósito: a validação
# é a de api.validacao, com mensagens em português, e não a do Pydantic.
# ---------------------------------------------------------------------------
class Registro(BaseModel):
    nome: Any = None
    cpf: Any = None
    email: Any = None
    idade: Any = None
    senha: Any = None


class NovoUsuario(Registro):
    papel: Any = "usuario"


class Edicao(BaseModel):
    nome: Any = None
    email: Any = None
    idade: Any = None
    papel: Any = None
    senha: Any = None  # vazio ou ausente = mantém a senha atual


class Login(BaseModel):
    login: Any = None
    senha: Any = None


class MeusDados(BaseModel):
    nome: Any = None
    email: Any = None
    idade: Any = None


class TrocaSenha(BaseModel):
    senha_atual: Any = None
    nova_senha: Any = None


# ---------------------------------------------------------------------------
# Autenticação
# ---------------------------------------------------------------------------
@roteador.get("/auth/regras")
def regras() -> dict[str, Any]:
    return {
        "idade_minima": config.IDADE_MINIMA,
        "idade_maxima": config.IDADE_MAXIMA,
        "nome_max": config.NOME_MAX_CARACTERES,
        "senha_min": config.SENHA_MIN_CARACTERES,
        "senha_max": config.SENHA_MAX_CARACTERES,
        "papeis": list(config.PAPEIS_USUARIO),
    }


@roteador.post("/auth/registro", status_code=status.HTTP_201_CREATED)
def registrar(body: Registro, con: banco.Conexao = Depends(conexao)) -> dict[str, Any]:
    valores, erros = validar(body.model_dump(), CAMPOS_REGISTRO)
    if erros:
        raise _erro_validacao(erros)
    try:
        usuario = banco.criar_usuario(con, **valores)  # cadastro público é sempre "usuario"
    except banco.Conflito as exc:
        raise _conflito(exc) from exc
    return {"token": banco.abrir_sessao(con, usuario["id"]), "usuario": serializar(usuario, cpf_completo=True)}


@roteador.post("/auth/login")
def entrar(body: Login, con: banco.Conexao = Depends(conexao)) -> dict[str, Any]:
    if not isinstance(body.login, str) or not isinstance(body.senha, str) or not body.login.strip() or not body.senha:
        raise _erro(422, "Informe e-mail ou CPF e a senha.")
    if minutos := banco.minutos_de_bloqueio(con, body.login):
        raise _erro(429, f"Muitas tentativas com senha errada. Tente de novo em {minutos} min.")
    usuario = banco.autenticar(con, body.login, body.senha)
    if usuario is None:
        banco.registrar_falha_login(con, body.login)
        con.commit()  # a falha precisa ficar gravada mesmo com o erro que vem a seguir
        if minutos := banco.minutos_de_bloqueio(con, body.login):
            raise _erro(429, f"Muitas tentativas com senha errada. Tente de novo em {minutos} min.")
        raise _erro(401, "E-mail/CPF ou senha incorretos.")
    banco.limpar_falhas_login(con, body.login)
    return {"token": banco.abrir_sessao(con, usuario["id"]), "usuario": serializar(usuario, cpf_completo=True)}


@roteador.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def sair(authorization: str | None = Header(default=None), con: banco.Conexao = Depends(conexao)) -> Response:
    banco.encerrar_sessao(con, _token(authorization))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@roteador.get("/auth/eu")
def eu(usuario: dict[str, Any] = Depends(usuario_logado)) -> dict[str, Any]:
    return serializar(usuario, cpf_completo=True)


@roteador.put("/auth/eu")
def editar_meus_dados(body: MeusDados, usuario: dict[str, Any] = Depends(usuario_logado),
                      con: banco.Conexao = Depends(conexao)) -> dict[str, Any]:
    """Nome, e-mail e idade. CPF e tipo de usuário não mudam por aqui."""
    valores, erros = validar(body.model_dump(), ["nome", "email", "idade"])
    if erros:
        raise _erro_validacao(erros)
    try:
        return serializar(banco.atualizar_usuario(con, usuario["id"], **valores), cpf_completo=True)  # type: ignore[arg-type]
    except banco.Conflito as exc:
        raise _conflito(exc) from exc


@roteador.post("/auth/senha")
def trocar_senha(body: TrocaSenha, usuario: dict[str, Any] = Depends(usuario_logado),
                 con: banco.Conexao = Depends(conexao)) -> dict[str, Any]:
    """Confere a senha atual, grava a nova, encerra os outros logins e devolve um token novo."""
    if not isinstance(body.senha_atual, str) or not banco.conferir_senha_do_usuario(con, usuario["id"], body.senha_atual):
        raise _erro(422, "A senha atual está incorreta.", {"senha_atual": "A senha atual está incorreta."})
    valores, erros = validar({"senha": body.nova_senha}, ["senha"])
    if erros:
        raise _erro_validacao({"nova_senha": erros["senha"]})
    if valores["senha"] == body.senha_atual:
        raise _erro(422, "A nova senha precisa ser diferente da atual.",
                    {"nova_senha": "A nova senha precisa ser diferente da atual."})
    atualizado = banco.atualizar_usuario(con, usuario["id"], senha=valores["senha"])  # derruba todas as sessões
    return {"token": banco.abrir_sessao(con, usuario["id"]), "usuario": serializar(atualizado, cpf_completo=True)}  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Gerenciamento (admin)
# ---------------------------------------------------------------------------
@roteador.get("/usuarios")
def listar(busca: str = "", excluidos: bool = False, _: dict[str, Any] = Depends(exigir_admin),
           con: banco.Conexao = Depends(conexao)) -> list[dict[str, Any]]:
    return [serializar(u) for u in banco.listar_usuarios(con, busca, excluidos)]


@roteador.post("/usuarios", status_code=status.HTTP_201_CREATED)
def criar(body: NovoUsuario, _: dict[str, Any] = Depends(exigir_admin),
          con: banco.Conexao = Depends(conexao)) -> dict[str, Any]:
    valores, erros = validar(body.model_dump(), [*CAMPOS_REGISTRO, "papel"])
    if erros:
        raise _erro_validacao(erros)
    try:
        return serializar(banco.criar_usuario(con, **valores), cpf_completo=True)
    except banco.Conflito as exc:
        raise _conflito(exc) from exc


def _existente(con: banco.Conexao, usuario_id: int, incluir_excluidos: bool = False) -> dict[str, Any]:
    usuario = banco.buscar_usuario(con, usuario_id, incluir_excluidos=True)
    if usuario is None:
        raise _erro(404, "Usuário não encontrado.")
    if usuario["excluido_em"] and not incluir_excluidos:
        raise _erro(409, "Esta conta está excluída. Restaure-a antes de alterá-la.")
    return usuario


@roteador.get("/usuarios/{usuario_id}")
def detalhar(usuario_id: int, _: dict[str, Any] = Depends(exigir_admin),
             con: banco.Conexao = Depends(conexao)) -> dict[str, Any]:
    return serializar(_existente(con, usuario_id, incluir_excluidos=True), cpf_completo=True)


@roteador.put("/usuarios/{usuario_id}")
def editar(usuario_id: int, body: Edicao, admin: dict[str, Any] = Depends(exigir_admin),
           con: banco.Conexao = Depends(conexao)) -> dict[str, Any]:
    _existente(con, usuario_id)
    dados = body.model_dump()
    campos = ["nome", "email", "idade", "papel"]
    if dados.get("senha") not in (None, ""):
        campos.append("senha")
    valores, erros = validar(dados, campos)
    if erros:
        raise _erro_validacao(erros)
    if usuario_id == admin["id"] and valores["papel"] != "admin":
        raise _erro(409, "Você não pode tirar o seu próprio acesso de administrador.",
                    {"papel": "Peça a outro administrador para fazer essa mudança."})
    try:
        return serializar(banco.atualizar_usuario(con, usuario_id, **valores), cpf_completo=True)  # type: ignore[arg-type]
    except banco.Conflito as exc:
        raise _conflito(exc) from exc


@roteador.delete("/usuarios/{usuario_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir(usuario_id: int, admin: dict[str, Any] = Depends(exigir_admin),
            con: banco.Conexao = Depends(conexao)) -> Response:
    if usuario_id == admin["id"]:
        raise _erro(409, "Você não pode excluir a sua própria conta.")
    _existente(con, usuario_id)
    banco.excluir_usuario(con, usuario_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@roteador.post("/usuarios/{usuario_id}/restaurar")
def restaurar(usuario_id: int, _: dict[str, Any] = Depends(exigir_admin),
              con: banco.Conexao = Depends(conexao)) -> dict[str, Any]:
    _existente(con, usuario_id, incluir_excluidos=True)
    usuario = banco.restaurar_usuario(con, usuario_id)
    if usuario is None:
        raise _erro(409, "Este usuário não está excluído.")
    return serializar(usuario, cpf_completo=True)


@roteador.delete("/usuarios/{usuario_id}/definitivo", status_code=status.HTTP_204_NO_CONTENT)
def apagar_definitivo(usuario_id: int, _: dict[str, Any] = Depends(exigir_admin),
                      con: banco.Conexao = Depends(conexao)) -> Response:
    if _existente(con, usuario_id, incluir_excluidos=True)["excluido_em"] is None:
        raise _erro(409, "Exclua a conta primeiro. A exclusão definitiva só vale para contas já excluídas.")
    banco.apagar_usuario_definitivo(con, usuario_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Linha de comando: cria o primeiro administrador (o cadastro pela tela é sempre comum)
# ---------------------------------------------------------------------------
def criar_admin(dados: dict[str, Any]) -> dict[str, Any]:
    valores, erros = validar(dados, CAMPOS_REGISTRO)
    if erros:
        raise ValueError("\n".join(f"- {m}" for m in erros.values()))
    with banco.conectar() as con:
        try:
            return banco.criar_usuario(con, **valores, papel="admin")
        except banco.Conflito as exc:
            raise ValueError(f"- {exc.mensagem}") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Gerencia usuários do Assessor pela linha de comando.")
    sub = parser.add_subparsers(dest="comando", required=True)
    sub.add_parser("criar-admin", help="cria um usuário administrador (pergunta os dados)")
    parser.parse_args(argv)

    print(f"Banco: {banco.url_banco().split('@')[-1]}")  # sem usuário e senha
    dados = {
        "nome": input("Nome completo: "),
        "cpf": input("CPF: "),
        "email": input("E-mail: "),
        "idade": input("Idade: "),
        "senha": getpass.getpass("Senha: "),
    }
    if getpass.getpass("Repita a senha: ") != dados["senha"]:
        print("As senhas não conferem.", file=sys.stderr)
        return 1
    try:
        usuario = criar_admin(dados)
    except ValueError as exc:
        print(f"Não foi possível criar o administrador:\n{exc}", file=sys.stderr)
        return 1
    print(f"Administrador criado: {usuario['nome']} <{usuario['email']}> (id {usuario['id']}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
