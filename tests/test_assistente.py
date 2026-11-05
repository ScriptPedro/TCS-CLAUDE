"""Testes do assessor conversacional (D37), sem rede: o Gemini é substituído por um provedor falso."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from api import main as api
from app import assistente
from app import components as ui
from src import advisor, config, llm, recommender, segmentation
from src.llm import ChamadaFerramenta, Mensagem, RespostaLLM
from tests.test_recommender import _signal_data

MODERADO = {
    **ui.respostas_padrao(),
    "idade": 41, "dependentes": "1_a_2", "renda_faixa": "4000_7000", "cartao_faixa": "10_30",
    "divida_cara": "nao", "reserva_faixa": "6_12", "conta_faixa": "mais_10", "objetivo": "aposentadoria",
    "prazo": "3_a_5_anos", "tolerancia": "manteria", "produtos": ["conta", "poupanca", "deposito"],
}
ENDIVIDADO = {**MODERADO, "idade": 23, "renda_faixa": "1500_2500", "cartao_faixa": "30_50",
              "divida_cara": "sim", "reserva_faixa": "nao_tenho", "produtos": ["conta", "cartao"]}
SAIU_DO_APERTO = {"divida_cara": "nao", "cartao_faixa": "ate_10", "reserva_faixa": "acima_12"}


class ProvedorFalso:
    """Devolve as respostas roteirizadas, em ordem, e guarda o que recebeu."""

    def __init__(self, roteiro: list[RespostaLLM]) -> None:
        self.roteiro = list(roteiro)
        self.chamadas: list[dict] = []

    def gerar(self, sistema: str, mensagens: list[Mensagem], ferramentas: list[llm.Ferramenta]) -> RespostaLLM:
        self.chamadas.append({"sistema": sistema, "mensagens": list(mensagens), "ferramentas": list(ferramentas)})
        return self.roteiro.pop(0) if len(self.roteiro) > 1 else self.roteiro[0]


def texto(t: str) -> RespostaLLM:
    return RespostaLLM(t, [])


def pede_simulacao(**alteracoes: object) -> RespostaLLM:
    return RespostaLLM("", [ChamadaFerramenta("simular_cenario", dict(alteracoes), "c1")])


@pytest.fixture(scope="module")
def models_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    tmp = tmp_path_factory.mktemp("assistente_models")
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


@pytest.fixture(scope="module")
def artefatos(models_dir: Path) -> advisor.Artefatos:
    return advisor.carregar_artefatos(models_dir / "segmentation.joblib", models_dir / "recommender.joblib",
                                      models_dir / "prep_stats.json")


def _rec(respostas: dict, artefatos: advisor.Artefatos) -> advisor.Recomendacao:
    q, erros = ui.montar_questionario(respostas)
    assert not erros
    return advisor.aconselhar(q, artefatos)


# ---------------------------------------------------------------------------
# Contexto e privacidade
# ---------------------------------------------------------------------------
def test_contexto_tem_os_numeros_do_assessor_e_so_faixas(artefatos: advisor.Artefatos) -> None:
    res = _rec(MODERADO, artefatos)
    ctx = assistente.contexto(res, MODERADO)
    assert "35 a 44 anos" in ctx and "41" not in ctx  # idade exata não sai do servidor
    assert "R$ 4.000 a R$ 7.000" in ctx               # renda só como faixa
    for classe, pct in res.carteira.alocacao.items():
        assert f"{config.CLASS_INFO[classe]['nome']}: {pct}%" in ctx
    assert res.carteira.perfil_efetivo in ctx and config.DISCLAIMER in ctx


def test_ferramenta_lista_opcoes_validas_e_nao_expoe_idade() -> None:
    (f,) = assistente.ferramentas()
    props = f.parametros["properties"]
    assert "idade" not in props
    assert props["divida_cara"]["enum"] == ui.PERGUNTAS["divida_cara"].opcoes
    assert props["produtos"]["type"] == "array"
    json.dumps(f.parametros)  # serializável para o fornecedor


# ---------------------------------------------------------------------------
# simular_cenario: números sempre do assessor
# ---------------------------------------------------------------------------
def test_simulacao_sai_do_modo_protecao(artefatos: advisor.Artefatos) -> None:
    base = _rec(ENDIVIDADO, artefatos)
    assert base.carteira.saude.modo_protecao
    r = assistente.simular_cenario(SAIU_DO_APERTO, ENDIVIDADO, base, artefatos)
    assert r["modo_protecao_antes"] is True and r["modo_protecao_depois"] is False
    assert sum(c["antes"] for c in r["carteira"]) == sum(c["depois"] for c in r["carteira"]) == 100
    novo = _rec({**ENDIVIDADO, **SAIU_DO_APERTO}, artefatos)
    assert {c["classe"]: c["depois"] for c in r["carteira"]} == novo.carteira.alocacao


@pytest.mark.parametrize("alteracoes", [{"divida_cara": "talvez_sim"}, {"idade": "60"}, {"inventado": "x"}, {}])
def test_simulacao_rejeita_valores_invalidos(alteracoes: dict, artefatos: advisor.Artefatos) -> None:
    base = _rec(MODERADO, artefatos)
    assert "erro" in assistente.simular_cenario(alteracoes, MODERADO, base, artefatos)


def test_simulacao_aceita_produto_unico_como_texto(artefatos: advisor.Artefatos) -> None:
    base = _rec(MODERADO, artefatos)
    r = assistente.simular_cenario({"produtos": "acoes"}, MODERADO, base, artefatos)
    assert "erro" not in r and r["perfil_depois"] in config.RISK_PROFILES


# ---------------------------------------------------------------------------
# Laço da conversa
# ---------------------------------------------------------------------------
def test_conversa_com_ferramenta(artefatos: advisor.Artefatos) -> None:
    prov = ProvedorFalso([pede_simulacao(**SAIU_DO_APERTO), texto("Sem a dívida, o modo proteção sai.")])
    r = assistente.conversar(ENDIVIDADO, [], "E se eu quitar tudo?", artefatos, prov)
    assert r.texto == "Sem a dívida, o modo proteção sai."
    assert len(r.simulacoes) == 1 and r.simulacoes[0]["modo_protecao_depois"] is False
    segunda = prov.chamadas[1]["mensagens"]
    assert [m.papel for m in segunda] == ["usuario", "modelo", "ferramenta"]
    assert segunda[-1].resultado == r.simulacoes[0] and segunda[-1].id_chamada == "c1"
    assert "CONTEXTO" in prov.chamadas[0]["sistema"] and "Nunca invente" in prov.chamadas[0]["sistema"]


def test_historico_e_limitado_e_convertido(artefatos: advisor.Artefatos) -> None:
    hist = [{"papel": "usuario" if i % 2 == 0 else "assistente", "texto": f"m{i}"} for i in range(30)]
    prov = ProvedorFalso([texto("ok")])
    assistente.conversar(MODERADO, hist, "Oi", artefatos, prov)
    msgs = prov.chamadas[0]["mensagens"]
    assert len(msgs) == config.ASSISTANT_MAX_HISTORY + 1
    assert msgs[-2].papel == "modelo" and msgs[-1].texto == "Oi"


def test_limite_de_rodadas_forca_resposta_final(artefatos: advisor.Artefatos) -> None:
    prov = ProvedorFalso([pede_simulacao(divida_cara="nao")] * config.ASSISTANT_MAX_TOOL_ROUNDS + [texto("fim")])
    r = assistente.conversar(MODERADO, [], "Simule", artefatos, prov)
    assert r.texto == "fim"
    assert len(prov.chamadas) == config.ASSISTANT_MAX_TOOL_ROUNDS + 1
    assert prov.chamadas[-1]["ferramentas"] == []  # última chamada sem ferramentas


def test_ferramenta_desconhecida_volta_como_erro(artefatos: advisor.Artefatos) -> None:
    prov = ProvedorFalso([RespostaLLM("", [ChamadaFerramenta("apagar_tudo", {})]), texto("ok")])
    r = assistente.conversar(MODERADO, [], "?", artefatos, prov)
    assert r.simulacoes == [] and "erro" in prov.chamadas[1]["mensagens"][-1].resultado


@pytest.mark.parametrize("pergunta", ["", "   ", "x" * (config.ASSISTANT_MAX_QUESTION_CHARS + 1)])
def test_pergunta_invalida(pergunta: str, artefatos: advisor.Artefatos) -> None:
    with pytest.raises(ValueError):
        assistente.conversar(MODERADO, [], pergunta, artefatos, ProvedorFalso([texto("x")]))


def test_sem_chave_fica_indisponivel(artefatos: advisor.Artefatos, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(config.LLM_API_KEY_ENV, raising=False)
    assert llm.obter_provedor() is None
    with pytest.raises(llm.AssistenteIndisponivel, match=config.LLM_API_KEY_ENV):
        assistente.conversar(MODERADO, [], "Oi", artefatos)


# ---------------------------------------------------------------------------
# Provedor Gemini (sem rede: o cliente do SDK é substituído)
# ---------------------------------------------------------------------------
def test_gemini_monta_conteudos_e_le_resposta(monkeypatch: pytest.MonkeyPatch) -> None:
    from google.genai import types

    monkeypatch.setenv(config.LLM_API_KEY_ENV, "chave-falsa")
    prov = llm.obter_provedor()
    assert isinstance(prov, llm.ProvedorGemini) and prov.modelo == config.LLM_DEFAULT_MODEL
    recebido = {}

    class Modelos:
        def generate_content(self, model, contents, config):  # noqa: A002 - assinatura do SDK
            recebido.update(model=model, contents=contents, config=config)
            return types.GenerateContentResponse(candidates=[types.Candidate(content=types.Content(role="model", parts=[
                types.Part(text="pensando", thought=True),
                types.Part(function_call=types.FunctionCall(id="a1", name="simular_cenario", args={"divida_cara": "nao"})),
            ]))])

    prov._cliente = type("Cliente", (), {"models": Modelos()})()
    msgs = [Mensagem("usuario", "oi"), Mensagem("modelo", "olá"),
            Mensagem("ferramenta", nome_ferramenta="simular_cenario", resultado={"x": 1}, id_chamada="z"),
            Mensagem("ferramenta", nome_ferramenta="simular_cenario", resultado={"x": 2}, id_chamada="w")]
    r = prov.gerar("sistema", msgs, assistente.ferramentas())
    assert r.texto == "" and r.chamadas == [ChamadaFerramenta("simular_cenario", {"divida_cara": "nao"}, "a1")]
    papeis = [c.role for c in recebido["contents"]]
    assert papeis == ["user", "model", "tool"] and len(recebido["contents"][-1].parts) == 2  # respostas paralelas juntas
    assert recebido["config"].automatic_function_calling.disable is True
    assert recebido["config"].tools[0].function_declarations[0].name == "simular_cenario"


@pytest.mark.parametrize(("codigo", "trecho"), [(429, "limite"), (403, "chave"), (500, "não respondeu")])
def test_gemini_erros_viram_mensagem_amigavel(codigo: int, trecho: str, monkeypatch: pytest.MonkeyPatch) -> None:
    from google.genai import errors

    monkeypatch.setenv(config.LLM_API_KEY_ENV, "chave-falsa")
    prov = llm.obter_provedor()

    class Modelos:
        def generate_content(self, **_):
            erro = errors.ClientError if codigo < 500 else errors.ServerError
            raise erro(codigo, {"error": {"code": codigo, "message": "x", "status": "X"}})

    prov._cliente = type("Cliente", (), {"models": Modelos()})()
    with pytest.raises(llm.AssistenteIndisponivel, match=trecho):
        prov.gerar("s", [Mensagem("usuario", "oi")], [])


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------
@pytest.fixture
def client(models_dir: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("ASSESSOR_MODELS_DIR", str(models_dir))
    monkeypatch.delenv(config.LLM_API_KEY_ENV, raising=False)
    return TestClient(api.app)


def test_api_conversa_desativada_sem_chave(client: TestClient) -> None:
    info = client.get("/api/conversa").json()
    assert info["ativo"] is False and info["sugestoes"] and "Gemini" in info["aviso"]
    assert client.get("/api/saude").json()["assistente"] is False
    r = client.post("/api/conversa", json={"respostas": MODERADO, "pergunta": "Oi"})
    assert r.status_code == 503 and config.LLM_API_KEY_ENV in r.json()["detail"]["erros"][0]


def test_api_conversa_com_provedor(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    prov = ProvedorFalso([pede_simulacao(**SAIU_DO_APERTO), texto("Resposta.")])
    monkeypatch.setattr(assistente, "obter_provedor", lambda: prov)
    assert client.get("/api/conversa").json()["ativo"] is True
    r = client.post("/api/conversa", json={"respostas": ENDIVIDADO, "historico": [], "pergunta": "E se?"})
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["resposta"] == "Resposta." and corpo["simulacoes"][0]["modo_protecao_depois"] is False


def test_api_conversa_erros(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(assistente, "obter_provedor", lambda: ProvedorFalso([texto("x")]))
    assert client.post("/api/conversa", json={"respostas": MODERADO, "pergunta": ""}).status_code == 422
    assert client.post("/api/conversa", json={"respostas": {**MODERADO, "idade": 12}, "pergunta": "Oi"}).status_code == 422

    class Falha:
        def gerar(self, *_):
            raise llm.AssistenteIndisponivel("fora do ar")

    monkeypatch.setattr(assistente, "obter_provedor", lambda: Falha())
    r = client.post("/api/conversa", json={"respostas": MODERADO, "pergunta": "Oi"})
    assert r.status_code == 503 and r.json()["detail"]["erros"] == ["fora do ar"]
