"""Banco de dados SQL dos usuários do sistema (D40, D41): PostgreSQL + SQL puro (psycopg 3).

Tabelas:
    usuarios — cadastro; ``excluido_em`` preenchido = excluído (soft delete: a linha fica
               no banco, some das listagens, não faz login e pode ser restaurada)
    sessoes  — tokens de login ativos; guarda só o hash SHA-256 do token
    tentativas_login — senhas erradas recentes por conta (ou pelo texto digitado, se a conta não existe)
    recomendacoes    — cada recomendação gerada, ligada a quem pediu (respostas e resultado em JSONB)

As tabelas são criadas na primeira conexão de cada processo (``CREATE ... IF NOT EXISTS``).
Senhas são guardadas com scrypt + sal aleatório (``hashlib``). O endereço do banco vem de
``ASSESSOR_DATABASE_URL`` ou ``config.DATABASE_URL``.
"""

from __future__ import annotations

import hashlib
import hmac
import math
import os
import secrets
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from typing import Any

import psycopg
from psycopg import errors
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from src import config

Conexao = psycopg.Connection[dict[str, Any]]

ESQUEMA = f"""
CREATE TABLE IF NOT EXISTS usuarios (
    id            BIGINT      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nome          TEXT        NOT NULL,
    cpf           CHAR(11)    NOT NULL UNIQUE CHECK (cpf ~ '^[0-9]{{11}}$'),
    email         TEXT        NOT NULL UNIQUE CHECK (email = lower(email)),
    idade         SMALLINT    NOT NULL CHECK (idade BETWEEN {config.IDADE_MINIMA} AND {config.IDADE_MAXIMA}),
    senha_hash    TEXT        NOT NULL,
    papel         TEXT        NOT NULL DEFAULT 'usuario'
                              CHECK (papel IN ({", ".join(f"'{p}'" for p in config.PAPEIS_USUARIO)})),
    criado_em     TIMESTAMPTZ NOT NULL,
    atualizado_em TIMESTAMPTZ NOT NULL,
    excluido_em   TIMESTAMPTZ
);
CREATE TABLE IF NOT EXISTS sessoes (
    token_hash TEXT        PRIMARY KEY,
    usuario_id BIGINT      NOT NULL REFERENCES usuarios(id),
    criada_em  TIMESTAMPTZ NOT NULL,
    expira_em  TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_sessoes_usuario ON sessoes(usuario_id);
CREATE TABLE IF NOT EXISTS tentativas_login (
    login   TEXT        NOT NULL,
    momento TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_tentativas_login ON tentativas_login(login, momento);
CREATE TABLE IF NOT EXISTS recomendacoes (
    id         BIGINT      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    usuario_id BIGINT      NOT NULL REFERENCES usuarios(id),
    criada_em  TIMESTAMPTZ NOT NULL,
    perfil     TEXT        NOT NULL,
    respostas  JSONB       NOT NULL,
    resultado  JSONB       NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_recomendacoes_usuario ON recomendacoes(usuario_id, id);
"""

TABELAS = ("recomendacoes", "tentativas_login", "sessoes", "usuarios")

# Colunas que saem para a API (nunca a senha)
COLUNAS = ("id", "nome", "cpf", "email", "idade", "papel", "criado_em", "atualizado_em", "excluido_em")
COLUNAS_PUBLICAS = ", ".join(COLUNAS)

# Endereços cujo esquema já foi conferido neste processo
_esquemas_prontos: set[str] = set()


class Conflito(Exception):
    """CPF ou e-mail já cadastrado. ``campo`` diz qual."""

    def __init__(self, campo: str, mensagem: str) -> None:
        super().__init__(mensagem)
        self.campo = campo
        self.mensagem = mensagem


class BancoIndisponivel(Exception):
    """O Postgres não respondeu (desligado, endereço ou senha errados)."""


def url_banco() -> str:
    return os.environ.get("ASSESSOR_DATABASE_URL", config.DATABASE_URL)


def agora() -> datetime:
    return datetime.now(UTC)


def criar_esquema(con: Conexao) -> None:
    # A trava evita que dois processos subindo juntos criem as mesmas tabelas ao mesmo tempo
    con.execute("SELECT pg_advisory_xact_lock(hashtext('assessor_esquema'))")
    con.execute(ESQUEMA)  # type: ignore[arg-type]


@contextmanager
def conectar(url: str | None = None) -> Iterator[Conexao]:
    """Uma conexão por requisição; confirma no fim ou desfaz se der erro."""
    url = url or url_banco()
    try:
        con = psycopg.connect(url, row_factory=dict_row, connect_timeout=config.DATABASE_TIMEOUT_S)
    except psycopg.OperationalError as exc:
        raise BancoIndisponivel(str(exc)) from exc
    with con:  # commit no fim, rollback se houver exceção, e fecha
        if url not in _esquemas_prontos:
            criar_esquema(con)
            con.commit()
            _esquemas_prontos.add(url)
        yield con


def limpar_tabelas(con: Conexao) -> None:
    """Apaga todos os dados e reinicia os ids (usado pelos testes)."""
    con.execute(f"TRUNCATE {', '.join(TABELAS)} RESTART IDENTITY CASCADE")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Senhas e tokens
# ---------------------------------------------------------------------------
def gerar_hash_senha(senha: str) -> str:
    sal = secrets.token_bytes(16)
    n, r, p = config.SCRYPT_N, config.SCRYPT_R, config.SCRYPT_P
    chave = hashlib.scrypt(senha.encode(), salt=sal, n=n, r=r, p=p)
    return f"scrypt${n}${r}${p}${sal.hex()}${chave.hex()}"


def conferir_senha(senha: str, guardado: str) -> bool:
    try:
        algoritmo, n, r, p, sal, chave = guardado.split("$")
    except ValueError:
        return False
    if algoritmo != "scrypt":
        return False
    calculada = hashlib.scrypt(senha.encode(), salt=bytes.fromhex(sal), n=int(n), r=int(r), p=int(p))
    return hmac.compare_digest(calculada.hex(), chave)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Usuários
# ---------------------------------------------------------------------------
def _iso(valor: Any) -> Any:
    return valor.isoformat(timespec="seconds") if isinstance(valor, datetime) else valor


def _publico(linha: dict[str, Any] | None) -> dict[str, Any] | None:
    """Linha do banco → dicionário da API, com datas em texto ISO 8601."""
    return None if linha is None else {k: _iso(linha[k]) for k in COLUNAS}


def _checar_unicos(con: Conexao, cpf: str | None, email: str | None, ignorar_id: int | None = None) -> None:
    """CPF e e-mail são únicos inclusive entre excluídos: excluído é restaurado, não recadastrado."""
    for campo, valor in (("cpf", cpf), ("email", email)):
        if valor is None:
            continue
        linha = con.execute(f"SELECT id, excluido_em FROM usuarios WHERE {campo} = %s", (valor,)).fetchone()  # type: ignore[arg-type]
        if linha is None or linha["id"] == ignorar_id:
            continue
        rotulo = "CPF" if campo == "cpf" else "e-mail"
        if linha["excluido_em"]:
            raise Conflito(campo, f"Este {rotulo} pertence a uma conta desativada. "
                                  "Fale com um administrador para reativá-la.")
        raise Conflito(campo, f"Já existe uma conta com este {rotulo}.")


def criar_usuario(con: Conexao, *, nome: str, cpf: str, email: str, idade: int, senha: str,
                  papel: str = "usuario") -> dict[str, Any]:
    _checar_unicos(con, cpf, email)
    momento = agora()
    try:
        with con.transaction():  # savepoint: se outra requisição gravar o mesmo CPF antes, só ele é desfeito
            linha = con.execute(
                f"INSERT INTO usuarios (nome, cpf, email, idade, senha_hash, papel, criado_em, atualizado_em) "
                f"VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING {COLUNAS_PUBLICAS}",  # type: ignore[arg-type]
                (nome, cpf, email, idade, gerar_hash_senha(senha), papel, momento, momento),
            ).fetchone()
    except errors.UniqueViolation:
        _checar_unicos(con, cpf, email)
        raise
    return _publico(linha)  # type: ignore[return-value]


def buscar_usuario(con: Conexao, usuario_id: int, incluir_excluidos: bool = False) -> dict[str, Any] | None:
    filtro = "" if incluir_excluidos else " AND excluido_em IS NULL"
    return _publico(con.execute(f"SELECT {COLUNAS_PUBLICAS} FROM usuarios WHERE id = %s{filtro}",  # type: ignore[arg-type]
                                (usuario_id,)).fetchone())


def listar_usuarios(con: Conexao, busca: str = "", incluir_excluidos: bool = False) -> list[dict[str, Any]]:
    condicoes: list[str] = []
    params: list[Any] = []
    if not incluir_excluidos:
        condicoes.append("excluido_em IS NULL")
    if busca.strip():
        # % e _ digitados na busca valem como texto, não como curinga do LIKE
        termo = busca.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        digitos = "".join(c for c in termo if c.isdigit())
        alvo = ["nome ILIKE %s", "email ILIKE %s"]
        params += [f"%{termo}%", f"%{termo}%"]
        if digitos:
            alvo.append("cpf LIKE %s")
            params.append(f"%{digitos}%")
        condicoes.append("(" + " OR ".join(alvo) + ")")
    onde = f" WHERE {' AND '.join(condicoes)}" if condicoes else ""
    linhas = con.execute(f"SELECT {COLUNAS_PUBLICAS} FROM usuarios{onde} ORDER BY lower(nome), id",  # type: ignore[arg-type]
                         params).fetchall()
    return [_publico(linha) for linha in linhas]  # type: ignore[misc]


def atualizar_usuario(con: Conexao, usuario_id: int, **campos: Any) -> dict[str, Any] | None:
    """Atualiza nome, e-mail, idade, papel e/ou senha de um usuário ativo. CPF não muda."""
    if buscar_usuario(con, usuario_id) is None:
        return None
    _checar_unicos(con, None, campos.get("email"), ignorar_id=usuario_id)
    if "senha" in campos:
        campos["senha_hash"] = gerar_hash_senha(campos.pop("senha"))
    permitidos = {"nome", "email", "idade", "papel", "senha_hash"}
    sets = {k: v for k, v in campos.items() if k in permitidos}
    if sets:
        atribuicoes = ", ".join(f"{k} = %s" for k in sets)
        try:
            with con.transaction():
                con.execute(f"UPDATE usuarios SET {atribuicoes}, atualizado_em = %s WHERE id = %s",  # type: ignore[arg-type]
                            (*sets.values(), agora(), usuario_id))
        except errors.UniqueViolation:
            _checar_unicos(con, None, campos.get("email"), ignorar_id=usuario_id)
            raise
    if "senha_hash" in sets:
        encerrar_sessoes(con, usuario_id)  # senha trocada derruba os logins abertos
    return buscar_usuario(con, usuario_id)


def excluir_usuario(con: Conexao, usuario_id: int) -> bool:
    """Soft delete: marca ``excluido_em`` e encerra as sessões. Devolve False se já não estava ativo."""
    momento = agora()
    cur = con.execute("UPDATE usuarios SET excluido_em = %s, atualizado_em = %s WHERE id = %s AND excluido_em IS NULL",
                      (momento, momento, usuario_id))
    if cur.rowcount:
        encerrar_sessoes(con, usuario_id)
    return bool(cur.rowcount)


def apagar_usuario_definitivo(con: Conexao, usuario_id: int) -> bool:
    """Exclusão física (pedido de eliminação da LGPD, art. 18, VI). Só vale para quem já está
    excluído (soft delete): são dois passos de propósito. Apaga também sessões, recomendações
    e tentativas de login da pessoa. Devolve False se o usuário não existe ou ainda está ativo."""
    linha = con.execute("SELECT id FROM usuarios WHERE id = %s AND excluido_em IS NOT NULL", (usuario_id,)).fetchone()
    if linha is None:
        return False
    con.execute("DELETE FROM sessoes WHERE usuario_id = %s", (usuario_id,))
    con.execute("DELETE FROM recomendacoes WHERE usuario_id = %s", (usuario_id,))
    con.execute("DELETE FROM tentativas_login WHERE login = %s", (f"usuario:{usuario_id}",))
    con.execute("DELETE FROM usuarios WHERE id = %s", (usuario_id,))
    return True


def restaurar_usuario(con: Conexao, usuario_id: int) -> dict[str, Any] | None:
    cur = con.execute("UPDATE usuarios SET excluido_em = NULL, atualizado_em = %s "
                      "WHERE id = %s AND excluido_em IS NOT NULL", (agora(), usuario_id))
    return buscar_usuario(con, usuario_id) if cur.rowcount else None


# ---------------------------------------------------------------------------
# Login e sessões
# ---------------------------------------------------------------------------
def chave_login(login: str) -> tuple[str, str]:
    """E-mail ou CPF digitado → (coluna, valor normalizado). "529.982.247-25" e "52998224725" são o mesmo login."""
    login = login.strip().lower()
    digitos = "".join(c for c in login if c.isdigit())
    if "@" not in login and len(digitos) == 11:
        return "cpf", digitos
    return "email", login


def autenticar(con: Conexao, login: str, senha: str) -> dict[str, Any] | None:
    """Login por e-mail ou CPF. Usuário excluído não entra."""
    campo, valor = chave_login(login)
    linha = con.execute(f"SELECT id, senha_hash FROM usuarios WHERE {campo} = %s AND excluido_em IS NULL",  # type: ignore[arg-type]
                        (valor,)).fetchone()
    if linha is None:
        gerar_hash_senha(senha)  # mesmo custo de tempo com ou sem usuário: não revela quem existe
        return None
    if not conferir_senha(senha, linha["senha_hash"]):
        return None
    return buscar_usuario(con, linha["id"])


def abrir_sessao(con: Conexao, usuario_id: int) -> str:
    token = secrets.token_urlsafe(32)
    criada = agora()
    expira = criada + timedelta(hours=config.SESSAO_HORAS)
    con.execute("DELETE FROM sessoes WHERE expira_em < %s", (criada,))
    con.execute("INSERT INTO sessoes (token_hash, usuario_id, criada_em, expira_em) VALUES (%s, %s, %s, %s)",
                (_hash_token(token), usuario_id, criada, expira))
    return token


def usuario_da_sessao(con: Conexao, token: str) -> dict[str, Any] | None:
    linha = con.execute(
        f"SELECT {', '.join('u.' + c for c in COLUNAS)} "  # type: ignore[arg-type]
        "FROM sessoes s JOIN usuarios u ON u.id = s.usuario_id "
        "WHERE s.token_hash = %s AND s.expira_em > %s AND u.excluido_em IS NULL",
        (_hash_token(token), agora()),
    ).fetchone()
    return _publico(linha)


def conferir_senha_do_usuario(con: Conexao, usuario_id: int, senha: str) -> bool:
    linha = con.execute("SELECT senha_hash FROM usuarios WHERE id = %s AND excluido_em IS NULL", (usuario_id,)).fetchone()
    return linha is not None and conferir_senha(senha, linha["senha_hash"])


def _chave_bloqueio(con: Conexao, login: str) -> str:
    """Conta existente → as falhas são da conta (errar pelo e-mail ou pelo CPF soma no mesmo
    contador); login que não existe → contador do próprio texto digitado."""
    campo, valor = chave_login(login)
    linha = con.execute(f"SELECT id FROM usuarios WHERE {campo} = %s", (valor,)).fetchone()  # type: ignore[arg-type]
    return f"usuario:{linha['id']}" if linha else f"{campo}:{valor}"


def minutos_de_bloqueio(con: Conexao, login: str) -> int:
    """Quantos minutos faltam para o login voltar a ser aceito (0 = liberado)."""
    chave = _chave_bloqueio(con, login)
    agora_ = agora()
    janela = timedelta(minutes=config.LOGIN_BLOQUEIO_MINUTOS)
    linha = con.execute("SELECT count(*) AS n, max(momento) AS ultima FROM tentativas_login "
                        "WHERE login = %s AND momento > %s", (chave, agora_ - janela)).fetchone()
    if linha is None or linha["n"] < config.LOGIN_MAX_TENTATIVAS:
        return 0
    libera = linha["ultima"] + janela
    return max(1, math.ceil((libera - agora_).total_seconds() / 60))


def registrar_falha_login(con: Conexao, login: str) -> None:
    chave = _chave_bloqueio(con, login)
    momento = agora()
    con.execute("DELETE FROM tentativas_login WHERE momento <= %s",
                (momento - timedelta(minutes=config.LOGIN_BLOQUEIO_MINUTOS),))
    con.execute("INSERT INTO tentativas_login (login, momento) VALUES (%s, %s)", (chave, momento))


def limpar_falhas_login(con: Conexao, login: str) -> None:
    con.execute("DELETE FROM tentativas_login WHERE login = %s", (_chave_bloqueio(con, login),))


def encerrar_sessao(con: Conexao, token: str) -> None:
    con.execute("DELETE FROM sessoes WHERE token_hash = %s", (_hash_token(token),))


def encerrar_sessoes(con: Conexao, usuario_id: int) -> None:
    con.execute("DELETE FROM sessoes WHERE usuario_id = %s", (usuario_id,))


# ---------------------------------------------------------------------------
# Recomendações (cada resultado fica ligado a quem o pediu)
# ---------------------------------------------------------------------------
def salvar_recomendacao(con: Conexao, usuario_id: int, perfil: str, respostas: dict[str, Any],
                        resultado: dict[str, Any]) -> int:
    linha = con.execute(
        "INSERT INTO recomendacoes (usuario_id, criada_em, perfil, respostas, resultado) "
        "VALUES (%s, %s, %s, %s, %s) RETURNING id",
        (usuario_id, agora(), perfil, Jsonb(respostas), Jsonb(resultado)),
    ).fetchone()
    return int(linha["id"])  # type: ignore[index]


def ultima_recomendacao(con: Conexao, usuario_id: int) -> dict[str, Any] | None:
    linha = con.execute("SELECT id, criada_em, perfil, respostas, resultado FROM recomendacoes "
                        "WHERE usuario_id = %s ORDER BY id DESC LIMIT 1", (usuario_id,)).fetchone()
    if linha is None:
        return None
    return {**linha, "criada_em": _iso(linha["criada_em"])}


def contar_recomendacoes(con: Conexao, usuario_id: int) -> int:
    linha = con.execute("SELECT count(*) AS n FROM recomendacoes WHERE usuario_id = %s", (usuario_id,)).fetchone()
    return int(linha["n"])  # type: ignore[index]
