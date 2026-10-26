"""Utilitários compartilhados (logging)."""

from __future__ import annotations

import logging

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
