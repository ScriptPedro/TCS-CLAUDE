"""Testes da API do front React: contrato do questionário e da recomendação."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from api import main as api
from app import components as ui
from src import config, raio_x, recommender, segmentation
from tests.fakes import write_fake_raio_x
from tests.test_recommender import _signal_data

MODERADO = {
    **ui.respostas_padrao(),
    "idade": 40, "dependentes": "1_a_2", "renda_faixa": "4500_10000", "cartao_faixa": "10_30",
    "divida_cara": "nao", "reserva_faixa": "6_12", "conta_faixa": "mais_10", "objetivo": "aposentadoria",
    "prazo": "3_a_5_anos", "tolerancia": "manteria", "produtos": ["conta", "poupanca", "deposito"],
}
ENDIVIDADO = {**MODERADO, "idade": 23, "renda_faixa": "1800_2500", "cartao_faixa": "30_50",
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
    raio_x.run(write_fake_raio_x(tmp / "raio_x.xlsx"), tmp / config.RAIO_X_FILE.name, tmp / "raio_x.md")
    return tmp


USUARIA = {"nome": "Ana Souza", "cpf": "111.444.777-35", "email": "ana@exemplo.com", "idade": 40, "senha": "senhaForte1"}


def _logado(monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest) -> TestClient:
    """Cliente já logado num banco de testes vazio: a recomendação exige login (D40)."""
    request.getfixturevalue("banco_postgres")  # pula o teste se não houver Postgres para testes
    monkeypatch.setattr(config, "SCRYPT_N", 2**8)
    c = TestClient(api.app)
    token = c.post("/api/auth/registro", json=USUARIA).json()["token"]
    c.headers.update({"Authorization": f"Bearer {token}"})
    return c


@pytest.fixture
def client(models_dir: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Sem login: questionário e saúde são públicos e não precisam do banco."""
    monkeypatch.setenv("ASSESSOR_MODELS_DIR", str(models_dir))
    return TestClient(api.app)


@pytest.fixture
def logado(models_dir: Path, monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest) -> TestClient:
    monkeypatch.setenv("ASSESSOR_MODELS_DIR", str(models_dir))
    return _logado(monkeypatch, request)


def test_questionario_tem_todas_as_perguntas(client: TestClient) -> None:
    r = client.get("/api/questionario").json()
    campos = [p["campo"] for e in r["etapas"] for p in e["perguntas"]]
    assert sorted(campos) == sorted(ui.PERGUNTAS)
    assert r["padrao"] == ui.respostas_padrao()
    renda = next(p for e in r["etapas"] for p in e["perguntas"] if p["campo"] == "renda_faixa")
    assert {"valor": "4500_10000", "rotulo": "R$ 4.500 a R$ 10.000"} in renda["opcoes"]


def test_saude_com_e_sem_modelos(client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert client.get("/api/saude").json()["modelos"] is True
    monkeypatch.setenv("ASSESSOR_MODELS_DIR", str(tmp_path))
    assert client.get("/api/saude").json()["modelos"] is False


def test_recomendacao_moderada(logado: TestClient) -> None:
    r = logado.post("/api/recomendacao", json={"respostas": MODERADO})
    assert r.status_code == 200
    res = r.json()
    assert sum(c["pct"] for c in res["carteira"]) == 100
    assert {c["classe"] for c in res["carteira"]} == set(config.BR_ASSET_CLASSES)
    assert len(res["resumo"]) == 3 and res["proximos_passos"]
    assert res["saude"]["modo_protecao"] is False
    for c in res["carteira"]:
        assert c["minimo"] <= c["pct"] <= c["maximo"] or c["pct"] == 0
    ref = res["referencia_br"]  # raio_x.json na pasta de modelos (D36)
    assert ref["faixa_idade"] == "35 a 44 anos" and ref["entrevistados"] >= 0
    assert {p["classe"] for p in ref["posse"]} == set(config.BR_ASSET_CLASSES)
    assert "Como brasileiros parecidos com você investem" in res["texto"]
    assert ref["linhas"] and [p["fracao"] for p in ref["posse"]] == sorted((p["fracao"] for p in ref["posse"]), reverse=True)
    assert "Raio X" in res["calculo"]["rotulo_afinidade"] and len(res["calculo"]["passos"]) == 3


def test_recomendacao_endividada_ativa_modo_protecao(logado: TestClient) -> None:
    res = logado.post("/api/recomendacao", json={"respostas": ENDIVIDADO}).json()
    assert res["saude"]["modo_protecao"] is True
    pct = {c["classe"]: c["pct"] for c in res["carteira"]}
    assert pct["acoes"] == 0 and pct["multimercado"] == 0


def test_respostas_invalidas_viram_422(logado: TestClient) -> None:
    r = logado.post("/api/recomendacao", json={"respostas": {**MODERADO, "idade": 12}})
    assert r.status_code == 422
    assert r.json()["detail"]["erros"]


def test_sem_modelos_vira_503(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest) -> None:
    monkeypatch.setenv("ASSESSOR_MODELS_DIR", str(tmp_path))
    r = _logado(monkeypatch, request).post("/api/recomendacao", json={"respostas": MODERADO})
    assert r.status_code == 503


def test_recomendacao_exige_login(client: TestClient) -> None:
    """Sem token, 401 antes de abrir o banco: vale mesmo sem Postgres."""
    assert client.post("/api/recomendacao", json={"respostas": MODERADO}).status_code == 401
    assert client.get("/api/recomendacoes/ultima").status_code == 401


def test_recomendacao_fica_salva_para_quem_pediu(logado: TestClient) -> None:
    assert logado.get("/api/recomendacoes/ultima").json() is None
    logado.post("/api/recomendacao", json={"respostas": MODERADO})
    res = logado.post("/api/recomendacao", json={"respostas": {**ENDIVIDADO, "lixo": "x" * 1000}}).json()
    ultima = logado.get("/api/recomendacoes/ultima").json()
    assert ultima["resultado"] == res and ultima["respostas"]["divida_cara"] == "sim"
    assert ultima["perfil"] == res["perfil"]["efetivo"]
    assert "lixo" not in ultima["respostas"]  # só as perguntas conhecidas vão para o banco
    # outra pessoa não vê a recomendação de ninguém
    outro = TestClient(api.app)
    token = outro.post("/api/auth/registro", json={**USUARIA, "cpf": "935.411.347-80", "email": "bruno@exemplo.com"}).json()["token"]
    assert outro.get("/api/recomendacoes/ultima", headers={"Authorization": f"Bearer {token}"}).json() is None
