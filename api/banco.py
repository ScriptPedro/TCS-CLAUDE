"""Banco de dados SQL dos usuários do sistema (D40): SQLite + SQL puro.

Tabelas:
    usuarios — cadastro; ``excluido_em`` preenchido = excluído (soft delete: a linha fica
               no banco, some das listagens, não faz login e pode ser restaurada)
    sessoes  — tokens de login ativos; guarda só o hash SHA-256 do token
    tentativas_login — senhas erradas recentes por conta (ou pelo texto digitado, se a conta não existe)
    recomendacoes    — cada recomendação gerada, ligada a quem pediu (respostas e resultado em JSON)

Senhas são guardadas com scrypt + sal aleatório (``hashlib``, sem dependência nova).
O arquivo vem de ``ASSESSOR_DB`` ou ``config.USUARIOS_DB_FILE``.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
import secrets
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from src import config

ESQUEMA = f"""
CREATE TABLE IF NOT EXISTS usuarios (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    nome          TEXT    NOT NULL,
    cpf           TEXT    NOT NULL UNIQUE CHECK (length(cpf) = 11),
    email         TEXT    NOT NULL UNIQUE,
    idade         INTEGER NOT NULL CHECK (idade BETWEEN {config.IDADE_MINIMA} AND {config.IDADE_MAXIMA}),
    senha_hash    TEXT    NOT NULL,
    papel         TEXT    NOT NULL DEFAULT 'usuario'
                          CHECK (papel IN ({", ".join(f"'{p}'" for p in config.PAPEIS_USUARIO)})),
    criado_em     TEXT    NOT NULL,
    atualizado_em TEXT    NOT NULL,
    excluido_em   TEXT
);
CREATE TABLE IF NOT EXISTS sessoes (
    token_hash TEXT    PRIMARY KEY,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
    criada_em  TEXT    NOT NULL,
    expira_em  TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_sessoes_usuario ON sessoes(usuario_id);
CREATE TABLE IF NOT EXISTS tentativas_login (
    login   TEXT NOT NULL,
    momento TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_tentativas_login ON tentativas_login(login, momento);
CREATE TABLE IF NOT EXISTS recomendacoes (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
    criada_em  TEXT    NOT NULL,
    perfil     TEXT    NOT NULL,
    respostas  TEXT    NOT NULL,
    resultado  TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_recomendacoes_usuario ON recomendacoes(usuario_id, id);
"""

# Colunas que saem para a API (nunca a senha)
COLUNAS_PUBLICAS = "id, nome, cpf, email, idade, papel, criado_em, atualizado_em, excluido_em"


class Conflito(Exception):
    """CPF ou e-mail já cadastrado. ``campo`` diz qual."""

    def __init__(self, campo: str, mensagem: str) -> None:
        super().__init__(mensagem)
        self.campo = campo
        self.mensagem = mensagem


def caminho_banco() -> Path:
    return Path(os.environ.get("ASSESSOR_DB", config.USUARIOS_DB_FILE))


def agora() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


@contextmanager
def conectar(caminho: Path | None = None) -> Iterator[sqlite3.Connection]:
    """Uma conexão por requisição; confirma no fim ou desfaz se der erro."""
    caminho = caminho or caminho_banco()
    caminho.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(caminho)
    con.row_factory = sqlite3.Row
    try:
        con.execute("PRAGMA foreign_keys = ON")
        con.executescript(ESQUEMA)
        yield con
        con.commit()
    except BaseException:
        con.rollback()
        raise
    finally:
        con.close()


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
def _publico(linha: sqlite3.Row | None) -> dict[str, Any] | None:
    return None if linha is None else dict(linha)


def _checar_unicos(con: sqlite3.Connection, cpf: str | None, email: str | None, ignorar_id: int | None = None) -> None:
    """CPF e e-mail são únicos inclusive entre excluídos: excluído é restaurado, não recadastrado."""
    for campo, valor in (("cpf", cpf), ("email", email)):
        if valor is None:
            continue
        linha = con.execute(f"SELECT id, excluido_em FROM usuarios WHERE {campo} = ?", (valor,)).fetchone()
        if linha is None or linha["id"] == ignorar_id:
            continue
        rotulo = "CPF" if campo == "cpf" else "e-mail"
        if linha["excluido_em"]:
            raise Conflito(campo, f"Este {rotulo} pertence a uma conta desativada. "
                                  "Fale com um administrador para reativá-la.")
        raise Conflito(campo, f"Já existe uma conta com este {rotulo}.")


def criar_usuario(con: sqlite3.Connection, *, nome: str, cpf: str, email: str, idade: int, senha: str,
                  papel: str = "usuario") -> dict[str, Any]:
    _checar_unicos(con, cpf, email)
    momento = agora()
    cur = con.execute(
        "INSERT INTO usuarios (nome, cpf, email, idade, senha_hash, papel, criado_em, atualizado_em) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (nome, cpf, email, idade, gerar_hash_senha(senha), papel, momento, momento),
    )
    return buscar_usuario(con, cur.lastrowid, incluir_excluidos=True)  # type: ignore[return-value]


def buscar_usuario(con: sqlite3.Connection, usuario_id: int, incluir_excluidos: bool = False) -> dict[str, Any] | None:
    filtro = "" if incluir_excluidos else " AND excluido_em IS NULL"
    return _publico(con.execute(f"SELECT {COLUNAS_PUBLICAS} FROM usuarios WHERE id = ?{filtro}",
                                (usuario_id,)).fetchone())


def listar_usuarios(con: sqlite3.Connection, busca: str = "", incluir_excluidos: bool = False) -> list[dict[str, Any]]:
    condicoes, params = [], []
    if not incluir_excluidos:
        condicoes.append("excluido_em IS NULL")
    if busca.strip():
        termo = busca.strip().lower()
        digitos = "".join(c for c in termo if c.isdigit())
        alvo = ["lower(nome) LIKE ?", "email LIKE ?"]
        params += [f"%{termo}%", f"%{termo}%"]
        if digitos:
            alvo.append("cpf LIKE ?")
            params.append(f"%{digitos}%")
        condicoes.append("(" + " OR ".join(alvo) + ")")
    onde = f" WHERE {' AND '.join(condicoes)}" if condicoes else ""
    linhas = con.execute(f"SELECT {COLUNAS_PUBLICAS} FROM usuarios{onde} ORDER BY lower(nome)", params).fetchall()
    return [dict(linha) for linha in linhas]


def atualizar_usuario(con: sqlite3.Connection, usuario_id: int, **campos: Any) -> dict[str, Any] | None:
    """Atualiza nome, e-mail, idade, papel e/ou senha de um usuário ativo. CPF não muda."""
    if buscar_usuario(con, usuario_id) is None:
        return None
    _checar_unicos(con, None, campos.get("email"), ignorar_id=usuario_id)
    if "senha" in campos:
        campos["senha_hash"] = gerar_hash_senha(campos.pop("senha"))
    permitidos = {"nome", "email", "idade", "papel", "senha_hash"}
    sets = {k: v for k, v in campos.items() if k in permitidos}
    if sets:
        atribuicoes = ", ".join(f"{k} = ?" for k in sets)
        con.execute(f"UPDATE usuarios SET {atribuicoes}, atualizado_em = ? WHERE id = ?",
                    (*sets.values(), agora(), usuario_id))
    if "senha_hash" in sets:
        encerrar_sessoes(con, usuario_id)  # senha trocada derruba os logins abertos
    return buscar_usuario(con, usuario_id)


def excluir_usuario(con: sqlite3.Connection, usuario_id: int) -> bool:
    """Soft delete: marca ``excluido_em`` e encerra as sessões. Devolve False se já não estava ativo."""
    momento = agora()
    cur = con.execute("UPDATE usuarios SET excluido_em = ?, atualizado_em = ? WHERE id = ? AND excluido_em IS NULL",
                      (momento, momento, usuario_id))
    if cur.rowcount:
        encerrar_sessoes(con, usuario_id)
    return bool(cur.rowcount)


def apagar_usuario_definitivo(con: sqlite3.Connection, usuario_id: int) -> bool:
    """Exclusão física (pedido de eliminação da LGPD, art. 18, VI). Só vale para quem já está
    excluído (soft delete): são dois passos de propósito. Apaga também sessões, recomendações
    e tentativas de login da pessoa. Devolve False se o usuário não existe ou ainda está ativo."""
    linha = con.execute("SELECT id FROM usuarios WHERE id = ? AND excluido_em IS NOT NULL", (usuario_id,)).fetchone()
    if linha is None:
        return False
    con.execute("DELETE FROM sessoes WHERE usuario_id = ?", (usuario_id,))
    con.execute("DELETE FROM recomendacoes WHERE usuario_id = ?", (usuario_id,))
    con.execute("DELETE FROM tentativas_login WHERE login = ?", (f"usuario:{usuario_id}",))
    con.execute("DELETE FROM usuarios WHERE id = ?", (usuario_id,))
    return True


def restaurar_usuario(con: sqlite3.Connection, usuario_id: int) -> dict[str, Any] | None:
    cur = con.execute("UPDATE usuarios SET excluido_em = NULL, atualizado_em = ? "
                      "WHERE id = ? AND excluido_em IS NOT NULL", (agora(), usuario_id))
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


def autenticar(con: sqlite3.Connection, login: str, senha: str) -> dict[str, Any] | None:
    """Login por e-mail ou CPF. Usuário excluído não entra."""
    campo, valor = chave_login(login)
    linha = con.execute(f"SELECT id, senha_hash FROM usuarios WHERE {campo} = ? AND excluido_em IS NULL",
                        (valor,)).fetchone()
    if linha is None:
        gerar_hash_senha(senha)  # mesmo custo de tempo com ou sem usuário: não revela quem existe
        return None
    if not conferir_senha(senha, linha["senha_hash"]):
        return None
    return buscar_usuario(con, linha["id"])


def abrir_sessao(con: sqlite3.Connection, usuario_id: int) -> str:
    token = secrets.token_urlsafe(32)
    criada = datetime.now(UTC)
    expira = criada + timedelta(hours=config.SESSAO_HORAS)
    con.execute("DELETE FROM sessoes WHERE expira_em < ?", (criada.isoformat(timespec="seconds"),))
    con.execute("INSERT INTO sessoes (token_hash, usuario_id, criada_em, expira_em) VALUES (?, ?, ?, ?)",
                (_hash_token(token), usuario_id, criada.isoformat(timespec="seconds"),
                 expira.isoformat(timespec="seconds")))
    return token


def usuario_da_sessao(con: sqlite3.Connection, token: str) -> dict[str, Any] | None:
    linha = con.execute(
        f"SELECT {', '.join('u.' + c.strip() for c in COLUNAS_PUBLICAS.split(','))} "
        "FROM sessoes s JOIN usuarios u ON u.id = s.usuario_id "
        "WHERE s.token_hash = ? AND s.expira_em > ? AND u.excluido_em IS NULL",
        (_hash_token(token), agora()),
    ).fetchone()
    return _publico(linha)


def conferir_senha_do_usuario(con: sqlite3.Connection, usuario_id: int, senha: str) -> bool:
    linha = con.execute("SELECT senha_hash FROM usuarios WHERE id = ? AND excluido_em IS NULL", (usuario_id,)).fetchone()
    return linha is not None and conferir_senha(senha, linha["senha_hash"])


def _chave_bloqueio(con: sqlite3.Connection, login: str) -> str:
    """Conta existente → as falhas são da conta (errar pelo e-mail ou pelo CPF soma no mesmo
    contador); login que não existe → contador do próprio texto digitado."""
    campo, valor = chave_login(login)
    linha = con.execute(f"SELECT id FROM usuarios WHERE {campo} = ?", (valor,)).fetchone()
    return f"usuario:{linha['id']}" if linha else f"{campo}:{valor}"


def minutos_de_bloqueio(con: sqlite3.Connection, login: str) -> int:
    """Quantos minutos faltam para o login voltar a ser aceito (0 = liberado)."""
    chave = _chave_bloqueio(con, login)
    agora_ = datetime.now(UTC)
    janela = timedelta(minutes=config.LOGIN_BLOQUEIO_MINUTOS)
    linhas = con.execute("SELECT momento FROM tentativas_login WHERE login = ? AND momento > ? ORDER BY momento",
                         (chave, (agora_ - janela).isoformat(timespec="seconds"))).fetchall()
    if len(linhas) < config.LOGIN_MAX_TENTATIVAS:
        return 0
    libera = datetime.fromisoformat(linhas[-1]["momento"]) + janela
    return max(1, math.ceil((libera - agora_).total_seconds() / 60))


def registrar_falha_login(con: sqlite3.Connection, login: str) -> None:
    chave = _chave_bloqueio(con, login)
    antigas = datetime.now(UTC) - timedelta(minutes=config.LOGIN_BLOQUEIO_MINUTOS)
    con.execute("DELETE FROM tentativas_login WHERE momento <= ?", (antigas.isoformat(timespec="seconds"),))
    con.execute("INSERT INTO tentativas_login (login, momento) VALUES (?, ?)", (chave, agora()))


def limpar_falhas_login(con: sqlite3.Connection, login: str) -> None:
    con.execute("DELETE FROM tentativas_login WHERE login = ?", (_chave_bloqueio(con, login),))


def encerrar_sessao(con: sqlite3.Connection, token: str) -> None:
    con.execute("DELETE FROM sessoes WHERE token_hash = ?", (_hash_token(token),))


def encerrar_sessoes(con: sqlite3.Connection, usuario_id: int) -> None:
    con.execute("DELETE FROM sessoes WHERE usuario_id = ?", (usuario_id,))


# ---------------------------------------------------------------------------
# Recomendações (cada resultado fica ligado a quem o pediu)
# ---------------------------------------------------------------------------
def salvar_recomendacao(con: sqlite3.Connection, usuario_id: int, perfil: str, respostas: dict[str, Any],
                        resultado: dict[str, Any]) -> int:
    cur = con.execute(
        "INSERT INTO recomendacoes (usuario_id, criada_em, perfil, respostas, resultado) VALUES (?, ?, ?, ?, ?)",
        (usuario_id, agora(), perfil, json.dumps(respostas, ensure_ascii=False), json.dumps(resultado, ensure_ascii=False)),
    )
    return int(cur.lastrowid)  # type: ignore[arg-type]


def ultima_recomendacao(con: sqlite3.Connection, usuario_id: int) -> dict[str, Any] | None:
    linha = con.execute("SELECT id, criada_em, perfil, respostas, resultado FROM recomendacoes "
                        "WHERE usuario_id = ? ORDER BY id DESC LIMIT 1", (usuario_id,)).fetchone()
    if linha is None:
        return None
    return {"id": linha["id"], "criada_em": linha["criada_em"], "perfil": linha["perfil"],
            "respostas": json.loads(linha["respostas"]), "resultado": json.loads(linha["resultado"])}


def contar_recomendacoes(con: sqlite3.Connection, usuario_id: int) -> int:
    return con.execute("SELECT count(*) FROM recomendacoes WHERE usuario_id = ?", (usuario_id,)).fetchone()[0]
