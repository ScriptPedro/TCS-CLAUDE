"""Testes das funções de limpeza da Etapa 2 (DataFrames pequenos e controlados)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src import config
from src import prepare_data as prep


def _raw_row(**overrides: object) -> dict[str, object]:
    """Linha bruta no formato do CSV (texto com espaços), com todos os produtos = 0."""
    row: dict[str, object] = {
        config.DATE_COL: "2016-05-28",
        config.ID_COL: 1,
        "age": " 35",
        "renta": "50000.0",
        "antiguedad": "    12",
        "sexo": "H",
        "segmento": "02 - PARTICULARES",
        "ind_actividad_cliente": "1",
        "ind_nuevo": "0",
        "canal_entrada": "KHE",
        **{c: 0.0 for c in config.PRODUCT_COLS},
    }
    row.update(overrides)
    return row


def _raw_df(rows: list[dict[str, object]]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    text_cols = [config.DATE_COL, *config.DEMOGRAPHIC_COLS]
    df[text_cols] = df[text_cols].astype("string")
    return df


def test_coerce_types_strips_and_converts() -> None:
    df = prep.coerce_types(_raw_df([_raw_row(age=" 35"), _raw_row(age=" NA", renta="NA")]))
    assert df["age"].tolist()[0] == 35
    assert df["age"].isna().tolist() == [False, True]
    assert df["renta"].isna().tolist() == [False, True]


def test_fill_maps_segment_and_fills_products() -> None:
    raw = _raw_df([_raw_row(segmento=None, ind_nomina_ult1=np.nan)])
    df = prep.fill_categoricals_and_products(prep.coerce_types(raw))
    assert df.loc[0, "segmento"] == config.UNKNOWN_LABEL
    assert df.loc[0, "ind_nomina_ult1"] == 0
    assert df["ind_nomina_ult1"].dtype == "int8"


@pytest.mark.parametrize("age, kept", [(17, False), (18, True), (100, True), (101, False)])
def test_filter_valid_age_limits(age: int, kept: bool) -> None:
    df = pd.DataFrame({"age": [float(age)]})
    out, removed = prep.filter_valid_age(df, config.AGE_MIN, config.AGE_MAX)
    assert (len(out) == 1) is kept
    assert removed == (0 if kept else 1)


def test_drop_duplicate_clients() -> None:
    df = pd.DataFrame({config.ID_COL: [1, 1, 2]})
    out, removed = prep.drop_duplicate_clients(df)
    assert removed == 1 and out[config.ID_COL].is_unique


def test_stratified_sample_preserves_proportions() -> None:
    df = pd.DataFrame({"segmento": ["a"] * 800 + ["b"] * 200, "x": range(1000)})
    out = prep.stratified_sample(df, 100, "segmento", config.RANDOM_STATE)
    assert len(out) == 100
    assert out["segmento"].value_counts()["b"] == 20


def test_antiguedad_negative_is_imputed_by_age_band() -> None:
    df = prep.add_age_band(
        pd.DataFrame({"age": [30, 30, 30], "antiguedad": [10.0, 20.0, -999999.0]})
    )
    stats = prep.PrepStats(snapshot_date=config.SNAPSHOT_DATE)
    out = prep.clean_antiguedad(df, stats)
    assert out["antiguedad"].tolist() == [10, 20, 15]
    assert out["antiguedad_imputada"].tolist() == [0, 0, 1]
    assert stats.antiguedad_negative == 1


def test_renta_winsorize_then_impute_by_group() -> None:
    n = 200
    df = prep.add_age_band(
        pd.DataFrame(
            {
                "age": [30] * n,
                "segmento": ["particulares"] * n,
                "renta": [*np.linspace(10_000, 100_000, n - 2), 1e9, np.nan],
            }
        )
    )
    stats = prep.PrepStats(snapshot_date=config.SNAPSHOT_DATE)
    out = prep.impute_renta(prep.winsorize_renta(df, stats), stats)

    _, high = stats.renta_winsor_limits
    assert out["renta"].max() <= high  # outlier de 1e9 foi limitado
    assert out["renta"].notna().all()
    assert out["renta_imputada"].sum() == 1
