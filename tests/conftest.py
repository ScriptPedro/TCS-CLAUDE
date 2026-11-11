"""Configuração comum dos testes."""

from __future__ import annotations

import glob
import os
import shutil
import subprocess
from collections.abc import Iterator
from pathlib import Path

import matplotlib
import pytest

# Os testes só salvam figuras em arquivo. Forçar o "Agg" evita depender do Tcl/Tk do
# Python instalado: no Windows, um Tcl/Tk quebrado gerava "Can't find a usable init.tcl"
# e travava o pytest (0x80000003) durante o garbage collection nos testes do Streamlit.
matplotlib.use("Agg", force=True)

from pytest_postgresql import factories  # noqa: E402

# ---------------------------------------------------------------------------
# PostgreSQL dos testes de usuários (D41)
#   1) ASSESSOR_TEST_DATABASE_URL definido → usa esse servidor (ex.: um Postgres no Docker).
#      CUIDADO: os testes APAGAM os dados das tabelas desse banco.
#   2) senão, sobe um Postgres temporário com o pg_ctl instalado na máquina (pytest-postgresql),
#      numa pasta temporária, e o derruba no fim.
#   3) sem nenhum dos dois, os testes que precisam de banco são pulados, com o motivo.
# ---------------------------------------------------------------------------
BANCO_DE_TESTE = "assessor_testes"


def _achar_pg_ctl() -> str | None:
    """pg_ctl no PATH, pelo pg_config ou nas pastas padrão do instalador do Windows."""
    if achado := shutil.which("pg_ctl"):
        return achado
    if shutil.which("pg_config"):
        try:
            pasta = subprocess.check_output(["pg_config", "--bindir"], text=True).strip()
        except (OSError, subprocess.CalledProcessError):
            pasta = ""
        for nome in ("pg_ctl", "pg_ctl.exe"):
            if pasta and (Path(pasta) / nome).exists():
                return str(Path(pasta) / nome)
    windows = sorted(glob.glob(r"C:\Program Files\PostgreSQL\*\bin\pg_ctl.exe"))
    return windows[-1] if windows else None


postgresql_temporario = factories.postgresql_proc(executable=_achar_pg_ctl(), port=None)

COMO_RESOLVER = (
    "Instale o PostgreSQL (o pytest sobe um servidor temporário sozinho) ou suba um no Docker e defina "
    "ASSESSOR_TEST_DATABASE_URL (veja o README)."
)


@pytest.fixture(scope="session")
def url_postgres_testes(request: pytest.FixtureRequest) -> Iterator[str]:
    """Endereço de um banco Postgres vazio, só para os testes."""
    if url := os.environ.get("ASSESSOR_TEST_DATABASE_URL"):
        yield url
        return
    if _achar_pg_ctl() is None:
        pytest.skip(f"Sem PostgreSQL para os testes de usuários. {COMO_RESOLVER}")
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        pytest.skip("O PostgreSQL não roda como root. Rode o pytest com outro usuário ou defina "
                    "ASSESSOR_TEST_DATABASE_URL (veja o README).")
    try:
        proc = request.getfixturevalue("postgresql_temporario")
    except Exception as exc:  # noqa: BLE001 — qualquer falha ao subir o servidor vira "pulado", com o motivo
        pytest.skip(f"Não foi possível subir o PostgreSQL temporário ({exc}). {COMO_RESOLVER}")

    import psycopg

    base = f"postgresql://{proc.user}@{proc.host}:{proc.port}"
    with psycopg.connect(f"{base}/postgres", autocommit=True) as con:
        con.execute(f"CREATE DATABASE {BANCO_DE_TESTE}")  # type: ignore[arg-type]
    yield f"{base}/{BANCO_DE_TESTE}"


@pytest.fixture
def banco_postgres(url_postgres_testes: str, monkeypatch: pytest.MonkeyPatch) -> str:
    """Aponta a API para o banco de testes, com as tabelas vazias e os ids reiniciados."""
    from api import banco

    monkeypatch.setenv("ASSESSOR_DATABASE_URL", url_postgres_testes)
    with banco.conectar(url_postgres_testes) as con:
        banco.limpar_tabelas(con)
    return url_postgres_testes
