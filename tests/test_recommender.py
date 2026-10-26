"""Testes da Etapa 5 (recomendação)."""

from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest

from src import config
from src import recommender as rec
from src.features import add_owned_flags, items_to_product_row


def _signal_data(n: int = 3000, seed: int = 0) -> pd.DataFrame:
    """Posse dirigida por renda individual e co-posse fundos → ações."""
    rng = np.random.default_rng(seed)
    renta = rng.lognormal(11.5, 0.6, n)
    z = (np.log(renta) - np.log(renta).mean()) / np.log(renta).std()
    sig = lambda x: 1 / (1 + np.exp(-x))  # noqa: E731
    df = pd.DataFrame({
        "age": rng.integers(18, 90, n), "renta": renta, "antiguedad": rng.integers(0, 250, n),
        "ind_actividad_cliente": rng.integers(0, 2, n),
        "segmento": rng.choice(["particulares", "universitario"], n),
    })
    for c in config.PRODUCT_COLS:
        df[c] = 0
    df["ind_cco_fin_ult1"] = 1
    df["ind_deco_fin_ult1"] = (rng.random(n) < sig(-1 + 1.5 * z)).astype(int)
    df["ind_fond_fin_ult1"] = (rng.random(n) < sig(-1.5 + 2 * z)).astype(int)
    df["ind_valo_fin_ult1"] = (rng.random(n) < sig(-2.5 + 3 * df["ind_fond_fin_ult1"])).astype(int)
    df["ind_plan_fin_ult1"] = (rng.random(n) < 0.1).astype(int)
    df["ind_ahor_fin_ult1"] = (rng.random(n) < sig(-1 - z)).astype(int)
    df["cluster"] = (df["segmento"] == "particulares").astype(int)  # cluster simples p/ o baseline
    return df


# ---------------------------------------------------------------------------
# Unidades
# ---------------------------------------------------------------------------
def test_features_for_excludes_own_item() -> None:
    for item in rec.ITEMS:
        cols = rec.features_for(item)
        assert f"possui_{item}" not in cols
        assert len(cols) == len(config.REC_NUMERIC_FEATURES) + len(config.REC_CATEGORICAL_FEATURES) + len(config.REC_OWNED_FEATURES) - 1


def test_items_to_product_row_roundtrip() -> None:
    row = pd.DataFrame([items_to_product_row({"conta", "fundos", "deposito"})])
    flags = add_owned_flags(row)
    assert flags["possui_fundos"].iat[0] == 1 and flags["possui_deposito"].iat[0] == 1
    assert flags["possui_acoes"].iat[0] == 0
    with pytest.raises(ValueError):
        items_to_product_row({"bitcoin"})


def test_precision_map_known_example() -> None:
    y = np.array([[1, 0, 1, 0, 0]])
    scores = np.array([[0.9, 0.8, 0.7, 0.1, 0.0]])  # ranking: item0 (✓), item1 (✗), item2 (✓)
    p3, m3 = rec.precision_map_at_k(y, scores, 3)
    assert p3 == pytest.approx(2 / 3)
    assert m3 == pytest.approx((1 / 1 + 2 / 3) / 2)
    p1, _ = rec.precision_map_at_k(y, scores, 1)
    assert p1 == 1.0


def test_precision_ignores_clients_without_items() -> None:
    y = np.array([[0, 0, 0, 0, 0], [1, 0, 0, 0, 0]])
    scores = np.array([[0.5] * 5, [0.9, 0.1, 0.1, 0.1, 0.1]])
    assert rec.precision_map_at_k(y, scores, 1) == (1.0, 1.0)


def test_leave_one_out_rank() -> None:
    scores = np.array([[0.1, 0.9, 0.5, 0.2, 0.3]])
    candidates = np.array([[True, False, True, True, True]])  # item 1 já possuído: fora do ranking
    out = rec.leave_one_out_metrics(scores, hidden=np.array([4]), candidates=candidates)
    assert out["hit@1"] == 0.0 and out["hit@3"] == 1.0  # item 4 fica em 2º, atrás do item 2
    assert out["mrr"] == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# Ponta a ponta
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def trained(tmp_path_factory: pytest.TempPathFactory) -> tuple[pd.DataFrame, Path]:
    tmp = tmp_path_factory.mktemp("rec")
    data = tmp / "in.parquet"
    _signal_data().to_parquet(data, index=False)
    model = tmp / "rec.joblib"
    comparison, _ = rec.run(data, model, tmp / "rel.md", tmp / "figs")
    return comparison, model


def test_lgbm_beats_baselines_when_signal_exists(trained: tuple[pd.DataFrame, Path]) -> None:
    comparison, _ = trained
    lgbm, cluster = comparison.loc["LightGBM"], comparison.loc["Popular no cluster"]
    assert lgbm["auc_media"] > cluster["auc_media"] + 0.05
    assert lgbm["loo_hit@1"] > cluster["loo_hit@1"]


def test_recommend_skips_owned_items(trained: tuple[pd.DataFrame, Path]) -> None:
    _, model = trained
    artifact = joblib.load(model)
    # Renda abaixo da média: nos dados plantados, P(ações | tem fundos) ≈ 0,62 e P(depósito) ≈ 0,10,
    # uma margem larga (com renda alta as duas ficam perto de 0,5 e a ordem vira ruído).
    user = pd.DataFrame([{
        "age": 40, "renta": 60_000, "antiguedad": 60, "ind_actividad_cliente": 1, "segmento": "particulares",
        **items_to_product_row({"conta", "fundos"}),
    }])
    recs = rec.recommend(artifact, user, k=3)[0]
    assert len(recs) == 3
    assert "fundos" not in [item for item, _ in recs]
    assert all(0 <= p <= 1 for _, p in recs)
    # Quem já tem fundos deve ter ações bem ranqueada (co-posse plantada nos dados)
    assert recs[0][0] == "acoes"


def test_explain_returns_top_factors(trained: tuple[pd.DataFrame, Path]) -> None:
    _, model = trained
    artifact = joblib.load(model)
    user = pd.DataFrame([{
        "age": 40, "renta": 150_000, "antiguedad": 60, "ind_actividad_cliente": 1, "segmento": "particulares",
        **items_to_product_row({"conta", "fundos"}),
    }])
    factors = rec.explain(artifact, user, "acoes", top_n=3)
    assert len(factors) == 3
    assert factors[0]["feature"] == "possui_fundos" and factors[0]["contribuicao"] > 0


def test_explain_label_reflects_flag_value(trained: tuple[pd.DataFrame, Path]) -> None:
    _, model = trained
    artifact = joblib.load(model)
    base = {"age": 40, "renta": 150_000, "antiguedad": 60, "ind_actividad_cliente": 1, "segmento": "particulares"}
    sem_fundos = pd.DataFrame([{**base, **items_to_product_row({"conta"})}])
    factors = rec.explain(artifact, sem_fundos, "acoes", top_n=5)
    fundos = next(f for f in factors if f["feature"] == "possui_fundos")
    assert fundos["rotulo"].startswith("Ainda não tem")  # nunca "Já tem" quando a flag é 0
    assert "CDB" in rec.FEATURE_LABELS["possui_deposito"]  # sigla preservada


def test_item_rarissimo_fica_sem_modelo_e_usa_taxa_media(tmp_path: Path) -> None:
    """Caso real: poupança tem ~4 positivos em 50 mil (D31). Antes, o treino quebrava."""
    df = _signal_data(n=2000, seed=3)
    df["ind_ahor_fin_ult1"] = 0
    df.loc[df.index[:3], "ind_ahor_fin_ult1"] = 1  # só 3 clientes com poupança
    data = tmp_path / "in.parquet"
    df.to_parquet(data, index=False)
    rec.run(data, tmp_path / "rec.joblib", tmp_path / "rel.md", tmp_path / "figs")

    artifact = joblib.load(tmp_path / "rec.joblib")
    assert "poupanca" not in artifact["models"] and artifact["skipped_items"] == ["poupanca"]
    assert "Poupança" in (tmp_path / "rel.md").read_text(encoding="utf-8").split("##")[0]

    user = pd.DataFrame([{
        "age": 40, "renta": 150_000, "antiguedad": 60, "ind_actividad_cliente": 1, "segmento": "particulares",
        **items_to_product_row({"conta"}),
    }])
    proba = rec.predict_proba(artifact, user)
    assert proba.loc[0, "poupanca"] == pytest.approx(artifact["baseline_global"]["poupanca"])
    assert rec.explain(artifact, user, "poupanca") == []
    assert len(rec.recommend(artifact, user, k=5)[0]) == 5
