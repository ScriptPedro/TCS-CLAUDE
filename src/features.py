"""Features derivadas da posse de produtos (usadas na EDA e na segmentação)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src import config


def add_group_counts(df: pd.DataFrame) -> pd.DataFrame:
    """Adiciona contagens de produtos por classe e indicadores agregados.

    Colunas criadas:
        - ``n_<classe>``: quantos produtos da classe o cliente possui;
        - ``n_produtos``: total de produtos;
        - ``possui_investimento``: 1 se tem ao menos um produto de
          renda fixa, renda variável ou previdência.
    """
    df = df.copy()
    for group, cols in config.PRODUCT_GROUPS.items():
        df[f"n_{group}"] = df[cols].sum(axis=1).astype("int8")
    df["n_produtos"] = df[config.PRODUCT_COLS].sum(axis=1).astype("int8")
    invest_cols = [f"n_{g}" for g in config.INVESTMENT_GROUPS]
    df["possui_investimento"] = (df[invest_cols].sum(axis=1) > 0).astype("int8")
    return df


def add_model_features(df: pd.DataFrame) -> pd.DataFrame:
    """Adiciona as features usadas pelos modelos (Etapas 4 e 5).

    - ``renta_log``: log da renda. A renda tem cauda longa; no log, a
      distância entre 20 mil e 40 mil pesa o mesmo que entre 100 mil e 200 mil.
    - contagens por classe (via :func:`add_group_counts`), se ainda não existirem.
    """
    if "n_produtos" not in df.columns:
        df = add_group_counts(df)
    else:
        df = df.copy()
    df["renta_log"] = np.log(df["renta"].astype(float))
    return df


def add_owned_flags(df: pd.DataFrame) -> pd.DataFrame:
    """Cria ``possui_<item>`` (0/1) para cada item do questionário (D16).

    Ex.: ``possui_deposito`` = 1 se o cliente tem depósito de curto, médio
    ou longo prazo. É a mesma granularidade que o usuário informa no app.
    """
    df = df.copy()
    for item, cols in config.QUESTIONNAIRE_ITEMS.items():
        df[f"possui_{item}"] = df[cols].max(axis=1).astype("int8")
    return df


def items_to_product_row(owned_items: set[str]) -> dict[str, int]:
    """Converte a resposta do questionário em 24 colunas de produto (0/1).

    Cada item marcado ativa o PRIMEIRO produto do seu grupo (ex.: "deposito"
    → depósito curto prazo). Assim, contagens por classe e flags ``possui_``
    ficam iguais às de um cliente real com esse produto.
    """
    unknown = owned_items - set(config.QUESTIONNAIRE_ITEMS)
    if unknown:
        raise ValueError(f"Itens desconhecidos no questionário: {sorted(unknown)}")
    row = {c: 0 for c in config.PRODUCT_COLS}
    for item in owned_items:
        row[config.QUESTIONNAIRE_ITEMS[item][0]] = 1
    return row
