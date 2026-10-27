"""Testes da API do front React: contrato do questionário e da recomendação."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from api import main as api
from app import components as ui
from src import config, recommender, segmentation
from tests.test_recommender import _signal_data

MODERADO = {
    **ui.respostas_padrao(),
    "idade": 40, "dependentes": "1_a_2", "renda_faixa": "4000_7000", "cartao_faixa": "10_30",
    "divida_cara": "nao", "reserva_faixa": "6_12", "conta_faixa": "mais_10", "objetivo": "aposentadoria",
    "prazo": "3_a_5_anos", "tolerancia": "manteria", "produtos": ["conta", "poupanca", "deposito"],
}
ENDIVIDADO = {**MODERADO, "idade": 23, "renda_faixa": "1500_2500", "cartao_faixa": "30_50",
              "divida_cara": "sim", "reserva_faixa": "nao_tenho", "produtos": ["conta", "cartao"]}


@pytest.fixture(scope="module")
def models_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    tmp = tmp_path_factory.mktemp("api_models")
    data = _signal_data(n=2000)
    data.drop(columns=["cluster"]).to_parquet(tmp / "base.parquet", index=False)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(config, "K_RANGE", range(2, 6))
        mp.setattr(config, "K_MIN_BUSINESS", 2)
        mp.setattr(config, "K_MAX_BUSINESS", 5)
        segmentation.run(tmp / "base.parquet", tmp / "segmentation.joblib", tmp / "clusters.parquet", tmp / "seg.md", tmp / "figs")
    recommender.run(tmp / "clusters.parquet", tmp / "recommender.joblib", tmp / "rec.md", tmp / "figs")
    edges = pd.qcut(data["renta"], 5, retbins=True)[1].tolist()
    (tmp / "prep_stats.json").write_text(json.dumps({"income_quantile_edges": edges}), encoding="utf-8")
    return tmp


@pytest.fixture
def client(models_dir: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("ASSESSOR_MODELS_DIR", str(models_dir))
    return TestClient(api.app)


def test_questionario_tem_todas_as_perguntas(client: TestClient) -> None:
    r = client.get("/api/questionario").json()
    campos = [p["campo"] for e in r["etapas"] for p in e["perguntas"]]
    assert sorted(campos) == sorted(ui.PERGUNTAS)
    assert r["padrao"] == ui.respostas_padrao()
    renda = next(p for e in r["etapas"] for p in e["perguntas"] if p["campo"] == "renda_faixa")
    assert {"valor": "4000_7000", "rotulo": "R$ 4.000 a R$ 7.000"} in renda["opcoes"]


def test_saude_com_e_sem_modelos(client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert client.get("/api/saude").json()["modelos"] is True
    monkeypatch.setenv("ASSESSOR_MODELS_DIR", str(tmp_path))
    assert client.get("/api/saude").json()["modelos"] is False


def test_recomendacao_moderada(client: TestClient) -> None:
    r = client.post("/api/recomendacao", json={"respostas": MODERADO})
    assert r.status_code == 200
    res = r.json()
    assert sum(c["pct"] for c in res["carteira"]) == 100
    assert {c["classe"] for c in res["carteira"]} == set(config.BR_ASSET_CLASSES)
    assert len(res["resumo"]) == 3 and res["proximos_passos"]
    assert res["saude"]["modo_protecao"] is False
    for c in res["carteira"]:
        assert c["minimo"] <= c["pct"] <= c["maximo"] or c["pct"] == 0


def test_recomendacao_endividada_ativa_modo_protecao(client: TestClient) -> None:
    res = client.post("/api/recomendacao", json={"respostas": ENDIVIDADO}).json()
    assert res["saude"]["modo_protecao"] is True
    pct = {c["classe"]: c["pct"] for c in res["carteira"]}
    assert pct["acoes"] == 0 and pct["multimercado"] == 0


def test_respostas_invalidas_viram_422(client: TestClient) -> None:
    r = client.post("/api/recomendacao", json={"respostas": {**MODERADO, "idade": 12}})
    assert r.status_code == 422
    assert r.json()["detail"]["erros"]


def test_sem_modelos_vira_503(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ASSESSOR_MODELS_DIR", str(tmp_path))
    r = TestClient(api.app).post("/api/recomendacao", json={"respostas": MODERADO})
    assert r.status_code == 503
