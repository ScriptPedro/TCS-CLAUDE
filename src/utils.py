"""Utilitários compartilhados (logging, formatação, backend de gráficos)."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from src import config


def get_logger(name: str) -> logging.Logger:
    """Retorna um logger configurado com o formato padrão do projeto.

    Args:
        name: nome do logger (normalmente ``__name__`` do módulo chamador).

    Returns:
        Logger pronto para uso, sem handlers duplicados.
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(config.LOG_FORMAT))
        logger.addHandler(handler)
        logger.setLevel(config.LOG_LEVEL)
        logger.propagate = False
    return logger


def fmt_num(valor: float, casas: int = 0) -> str:
    """Número no padrão brasileiro: 30000 → '30.000'; 2.5 (casas=1) → '2,5'."""
    texto = f"{valor:,.{casas}f}"
    return texto.replace(",", "§").replace(".", ",").replace("§", ".")


def fmt_brl(valor: float) -> str:
    """Valor em reais sem centavos: 30000 → 'R$ 30.000'."""
    return f"R$ {fmt_num(valor)}"


def caminho_relativo(alvo: Path, pasta_do_relatorio: Path) -> str:
    """Caminho de ``alvo`` relativo à pasta do relatório, com "/" (link Markdown portátil).

    Links absolutos (ex.: ``C:/Users/...``) quebram no GitHub e em outra máquina. Se não houver
    caminho relativo (drives diferentes no Windows), devolve o absoluto.
    """
    try:
        return Path(os.path.relpath(Path(alvo).resolve(), Path(pasta_do_relatorio).resolve())).as_posix()
    except ValueError:
        return Path(alvo).as_posix()


def usar_backend_sem_janela() -> None:
    """Usa o backend "Agg" do matplotlib: os gráficos são só salvos em arquivo.

    Sem isso, no Windows o matplotlib escolhe o TkAgg, que depende do Tcl/Tk. Em
    instalações com Tcl/Tk ausente ou quebrado, isso gera "Can't find a usable
    init.tcl" ou derruba o Python (0x80000003) quando uma figura é coletada pelo
    garbage collector em outra thread. Quem definir MPLBACKEND mantém a escolha.
    """
    if "MPLBACKEND" not in os.environ:
        import matplotlib

        matplotlib.use("Agg")
