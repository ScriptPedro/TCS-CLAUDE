"""Testes da Etapa 4 (segmentação)."""

from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest
from sklearn.metrics import adjusted_rand_score

from src import config
from src import segmentation as seg


def _personas(n_per: int = 150, seed: int = 0) -> pd.DataFrame:
    """Três grupos bem separados: jovem só conta, adulto, investidor de alta renda."""
    rng = np.random.default_rng(seed)
    specs = [  # (idade, renda, antiguidade, segmento, prob. de produtos de investimento)
        (23, 50_000, 20, "universitario", 0.0),
        (42, 90_000, 90, "particulares", 0.05),
        (55, 300_000, 170, "top", 0.6),
    ]
    frames = []
    for gid, (age, renta, ant, segmento, p_inv) in enumerate(specs):
        d = pd.DataFrame({
            "age": rng.normal(age, 2, n_per).round(),
            "renta": rng.lognormal(np.log(renta), 0.1, n_per),
            "antiguedad": rng.normal(ant, 5, n_per).round(),
            "ind_actividad_cliente": 1,
            "segmento": segmento,
            "grupo_real": gid,
        })
        for g, cols in config.PRODUCT_GROUPS.items():
            p = 0.5 if g == "liquidez" else (p_inv if g in config.INVESTMENT_GROUPS else 0.05)
            for c in cols:
                d[c] = (rng.random(n_per) < p).astype("int8")
        frames.append(d)
    return pd.concat(frames, ignore_index=True)


def test_elbow_k_finds_knee() -> None:
    metrics = pd.DataFrame({"inercia": [100, 30, 25, 22, 20, 19]}, index=range(2, 8))
    assert seg.elbow_k(metrics) == 3


def test_choose_k_respects_business_range() -> None:
    metrics = pd.DataFrame({"silhouette": [0.9, 0.3, 0.5, 0.4]}, index=[2, 3, 4, 5])
    assert seg.choose_k(metrics, k_min=3, k_max=5) == 4  # k=2 tem a maior, mas está fora da faixa
    with pytest.raises(ValueError):
        seg.choose_k(metrics, k_min=8, k_max=9)


def test_relabel_by_size_puts_largest_first() -> None:
    mapping = seg.relabel_by_size(np.array([2, 2, 2, 0, 1, 1]))
    assert mapping == {2: 0, 1: 1, 0: 2}


def test_bounded_features_are_scaled_0_1() -> None:
    df = seg.prepare_features(_personas())
    X = seg.build_preprocessor().fit_transform(df)
    n_cont = len(config.SEG_CONTINUOUS_FEATURES)
    bounded = X[:, n_cont : n_cont + len(config.SEG_BOUNDED_FEATURES)]
    assert bounded.min() >= 0 and bounded.max() <= 1


def test_name_override(monkeypatch: pytest.MonkeyPatch) -> None:
    df = seg.prepare_features(_personas())
    labels = df["grupo_real"].to_numpy()
    profile = seg.profile_clusters(df, labels)
    monkeypatch.setattr(config, "CLUSTER_NAME_OVERRIDES", {0: "Universitário digital"})
    names = seg.name_clusters(profile, df)
    assert names[0]["nome"] == "Universitário digital"
    assert len({v["nome"] for v in names.values()}) == len(names)  # nomes únicos


@pytest.fixture
def small_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[seg.SegmentationResult, Path, Path]:
    monkeypatch.setattr(config, "K_RANGE", range(2, 6))
    monkeypatch.setattr(config, "K_MIN_BUSINESS", 2)
    monkeypatch.setattr(config, "K_MAX_BUSINESS", 5)
    data = tmp_path / "in.parquet"
    _personas().to_parquet(data, index=False)
    model, out = tmp_path / "seg.joblib", tmp_path / "out.parquet"
    res = seg.run(data, model, out, tmp_path / "rel.md", tmp_path / "figs")
    return res, model, out


def test_end_to_end_recovers_groups(small_run: tuple[seg.SegmentationResult, Path, Path]) -> None:
    res, _, out = small_run
    clustered = pd.read_parquet(out)
    assert res.k == 3
    assert adjusted_rand_score(clustered["grupo_real"], clustered["cluster"]) > 0.95


def test_assign_cluster_matches_training_labels(small_run: tuple[seg.SegmentationResult, Path, Path]) -> None:
    _, model, out = small_run
    artifact = joblib.load(model)
    clustered = pd.read_parquet(out)
    predicted = seg.assign_cluster(artifact, clustered.drop(columns=["cluster"]))
    assert (predicted == clustered["cluster"].to_numpy()).all()
