"""Testes das features por classe e das tabelas da EDA."""

from __future__ import annotations

import pandas as pd

from src import config, eda
from src.features import add_group_counts


def _clients(products: list[list[str]]) -> pd.DataFrame:
    """Um cliente por lista de produtos possuídos."""
    rows = [{c: int(c in owned) for c in config.PRODUCT_COLS} for owned in products]
    return pd.DataFrame(rows)


def test_add_group_counts() -> None:
    df = add_group_counts(
        _clients([
            ["ind_cco_fin_ult1"],
            ["ind_cco_fin_ult1", "ind_fond_fin_ult1", "ind_tjcr_fin_ult1"],
            [],
        ])
    )
    assert df["n_liquidez"].tolist() == [1, 1, 0]
    assert df["n_renda_variavel"].tolist() == [0, 1, 0]
    assert df["n_produtos"].tolist() == [1, 3, 0]
    # Crédito não conta como investimento
    assert df["possui_investimento"].tolist() == [0, 1, 0]


def test_group_penetration_by() -> None:
    df = add_group_counts(_clients([["ind_fond_fin_ult1"], [], [], ["ind_plan_fin_ult1"]]))
    df["segmento"] = ["top", "top", "particulares", "particulares"]
    table = eda.group_penetration_by(df, "segmento")
    assert table.loc["top", "investimento"] == 50.0
    assert table.loc["particulares", "longo_prazo"] == 50.0


def test_top_correlated_pairs_finds_identical_products() -> None:
    owned = [["ind_cno_fin_ult1", "ind_nomina_ult1"], ["ind_cco_fin_ult1"], [], ["ind_cno_fin_ult1", "ind_nomina_ult1"]]
    pair = eda.top_correlated_pairs(_clients(owned), 1).iloc[0]
    assert {pair.produto_a, pair.produto_b} == {"Conta salário", "Folha de pagamento"}
    assert pair.phi == 1.0
