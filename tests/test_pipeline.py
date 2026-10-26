"""Teste de integração: CSV bruto sintético → todas as etapas → relatórios e app."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src import config, pipeline
from tests.fakes import write_fake_raw_csv

SAMPLE = 1_500


@pytest.fixture(scope="module")
def executado(tmp_path_factory: pytest.TempPathFactory) -> tuple[dict, pipeline.Paths]:
    root = tmp_path_factory.mktemp("pipeline")
    raw = write_fake_raw_csv(root / "train_ver2.csv")
    paths = pipeline.Paths.under(root / "saida")
    with pytest.MonkeyPatch.context() as mp:  # menos k avaliados = teste rápido
        mp.setattr(config, "K_RANGE", range(2, 7))
        mp.setattr(config, "K_MIN_BUSINESS", 3)
        mp.setattr(config, "K_MAX_BUSINESS", 6)
        resumo = pipeline.run(raw, paths, sample_size=SAMPLE)
    return resumo, paths


def test_todas_as_saidas_existem(executado: tuple[dict, pipeline.Paths]) -> None:
    _, paths = executado
    for campo in pipeline.Paths.__dataclass_fields__:
        assert Path(getattr(paths, campo)).exists(), campo
    figuras = {p.stem for p in paths.figures.glob("*.png")}
    assert {"11_escolha_k", "13_perfil_clusters", "15_comparacao_modelos", "17_shap_importancia"} <= figuras


def test_amostra_limpa_e_unica(executado: tuple[dict, pipeline.Paths]) -> None:
    _, paths = executado
    df = pd.read_parquet(paths.processed)
    assert len(df) == SAMPLE and df["ncodpers"].is_unique
    assert df.isna().sum().sum() == 0
    assert df["age"].between(config.AGE_MIN, config.AGE_MAX).all()


def test_personas_passam_e_resumo_coerente(executado: tuple[dict, pipeline.Paths]) -> None:
    resumo, paths = executado
    assert resumo["falhas_personas"] == {}
    assert 3 <= resumo["k"] <= 6
    assert 0.5 <= resumo["auc_lgbm"] <= 1.0
    assert "todas as verificações passaram" in paths.personas_report.read_text(encoding="utf-8")


def test_auditoria_de_vies_gerada(executado: tuple[dict, pipeline.Paths]) -> None:
    _, paths = executado
    texto = paths.audit_report.read_text(encoding="utf-8")
    assert "V de Cramér" in texto and "razao_impacto" in texto and "DENTRO de cada faixa" in texto


def test_paths_under_nao_toca_o_projeto(tmp_path: Path) -> None:
    paths = pipeline.Paths.under(tmp_path)
    for campo in pipeline.Paths.__dataclass_fields__:
        assert tmp_path in Path(getattr(paths, campo)).parents
