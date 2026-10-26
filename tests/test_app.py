"""Testes da Etapa 7: componentes do app e fluxo completo com streamlit.testing.AppTest."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from app import components as ui
from src import config, recommender, segmentation
from tests.test_recommender import _signal_data

APP = str(Path(__file__).resolve().parents[1] / "app" / "main.py")

# Respostas no formato do formulário (faixas)
MODERADO = {
    **ui.respostas_padrao(),
    "idade": 40, "dependentes": "1_a_2", "estabilidade_renda": "estavel", "renda_faixa": "4000_7000",
    "cartao_faixa": "10_30", "divida_cara": "nao", "reserva_faixa": "6_12", "conta_faixa": "mais_10",
    "objetivo": "aposentadoria", "prazo": "3_a_5_anos", "necessidade_liquidez": "nao",
    "tolerancia": "manteria", "conhecimento": "basico", "produtos": ["conta", "poupanca", "deposito"],
}
ENDIVIDADO = {
    **MODERADO, "idade": 23, "dependentes": "nenhum", "renda_faixa": "1500_2500", "cartao_faixa": "30_50",
    "divida_cara": "sim", "reserva_faixa": "nao_tenho", "conta_faixa": "1_5", "objetivo": "comprar_bem",
    "prazo": "1_a_3_anos", "tolerancia": "venderia_parte", "conhecimento": "nenhum", "produtos": ["conta", "cartao"],
}


# ---------------------------------------------------------------------------
# Componentes
# ---------------------------------------------------------------------------
def test_toda_pergunta_esta_em_uma_etapa() -> None:
    campos = [c for _, _, cs in ui.ETAPAS for c in cs]
    assert sorted(campos) == sorted(ui.PERGUNTAS) and len(campos) == len(set(campos))


def test_padroes_sao_opcoes_validas() -> None:
    for campo, p in ui.PERGUNTAS.items():
        if p.tipo in ("faixa", "opcao"):
            assert p.padrao in p.opcoes, campo
    q, erros = ui.montar_questionario(ui.respostas_padrao())
    assert erros == [] and q is not None


def test_faixas_viram_valores_representativos() -> None:
    q, erros = ui.montar_questionario(MODERADO)
    assert erros == []
    assert q.renda_mensal == 5_500
    assert q.gasto_cartao_mensal == pytest.approx(0.20 * 5_500)
    assert q.reserva_emergencia == pytest.approx(9.0 * 5_500)
    assert q.produtos == frozenset({"conta", "poupanca", "deposito"})


@pytest.mark.parametrize("faixa, cartao_alto", [("10_30", False), ("30_50", True)])
def test_borda_da_faixa_decide_a_regra_do_cartao(faixa: str, cartao_alto: bool) -> None:
    from src.portfolio import avaliar_saude
    q, _ = ui.montar_questionario({**MODERADO, "cartao_faixa": faixa})
    assert avaliar_saude(q).cartao_alto is cartao_alto


def test_tempo_de_conta_nao_passa_da_idade() -> None:
    q, erros = ui.montar_questionario({**MODERADO, "idade": 18, "conta_faixa": "mais_10"})
    assert erros == [] and q.anos_conta <= 2


def test_respostas_incompletas_viram_mensagem() -> None:
    q, erros = ui.montar_questionario({"idade": 30})
    assert q is None and "Responda todas" in erros[0]


def test_avisos_de_consistencia() -> None:
    q, _ = ui.montar_questionario({**MODERADO, "objetivo": "reserva", "prazo": "mais_de_5_anos"})
    assert any("Reserva de emergência" in a for a in ui.avisos_de_consistencia(q))


def test_grafico_omite_classes_zeradas() -> None:
    fig = ui.grafico_carteira({"liquidez": 66, "renda_fixa": 34, "multimercado": 0, "acoes": 0, "previdencia": 0})
    pie = fig.data[0]
    assert list(pie.values) == [66, 34]
    assert list(pie.marker.colors) == [ui.CLASS_COLORS["liquidez"], ui.CLASS_COLORS["renda_fixa"]]


def test_toda_classe_tem_cor_rotulo_e_informacao() -> None:
    assert set(ui.CLASS_COLORS) == set(ui.CLASS_SHORT_LABELS) == set(config.BR_ASSET_CLASSES) == set(config.CLASS_INFO)


# ---------------------------------------------------------------------------
# Fluxo completo (modelos pequenos treinados em dados sintéticos)
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def models_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    tmp = tmp_path_factory.mktemp("app_models")
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
def app(models_dir: Path, monkeypatch: pytest.MonkeyPatch) -> AppTest:
    monkeypatch.setenv("ASSESSOR_MODELS_DIR", str(models_dir))
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    return at


def _definir(at: AppTest, campo: str, valor: object) -> None:
    tipo = ui.PERGUNTAS[campo].tipo
    chave = f"w_{campo}"
    widget = {"faixa": at.select_slider, "opcao": at.radio, "numero": at.number_input, "multipla": at.multiselect}[tipo]
    widget(key=chave).set_value(valor)


def _preencher(at: AppTest, respostas: dict) -> None:
    """Percorre as 4 etapas como um usuário: responde e clica em Avançar."""
    for i, (_, _, campos) in enumerate(ui.ETAPAS):
        for campo in campos:
            _definir(at, campo, respostas[campo])
        botao = "btn_ver" if i == len(ui.ETAPAS) - 1 else "btn_avancar"
        at.button(key=botao).click()
        at.run()


def test_tela_inicial_mostra_etapa_1_e_aviso(app: AppTest) -> None:
    assert not app.exception
    assert any(config.DISCLAIMER in w.value for w in app.warning)
    assert app.subheader[0].value == "Sobre você"
    assert [b.key for b in app.button] == ["btn_avancar"]  # sem "Voltar" na primeira etapa
    assert not app.number_input(key="w_idade").value is None


def test_voltar_preserva_respostas(app: AppTest) -> None:
    _definir(app, "renda_faixa", "7000_12000")
    app.button(key="btn_avancar").click()
    app.run()
    assert app.subheader[0].value == "Suas finanças"
    app.button(key="btn_voltar").click()
    app.run()
    assert app.select_slider(key="w_renda_faixa").value == "7000_12000"


def test_persona_endividada_ativa_modo_protecao(app: AppTest) -> None:
    _preencher(app, ENDIVIDADO)
    assert not app.exception
    res = app.session_state["resultado"]
    assert res.carteira.saude.modo_protecao and res.carteira.saude.divida_cara
    assert app.metric[0].value == "Conservador"
    assert any("Modo proteção" in e.value for e in app.error)
    assert res.carteira.alocacao["acoes"] == 0


def test_persona_moderada_mostra_carteira_explicada(app: AppTest) -> None:
    _preencher(app, MODERADO)
    assert not app.exception
    assert app.header[0].value == "Sua recomendação"
    assert app.metric[0].value == "Moderado"
    res = app.session_state["resultado"]
    assert sum(res.carteira.alocacao.values()) == 100
    textos = " ".join(m.value for m in app.markdown)
    assert "Em resumo" in textos and "Próximos passos" in " ".join(s.value for s in app.subheader)
    assert res.cluster_nome in textos  # segmento em texto, não em st.metric
    # "$" escapado: sem isso o Markdown renderiza "R$ 640 de cada R$ 1.000" como fórmula LaTeX
    assert any("de cada R\\$ 1.000" in p.proto.text for p in app.get("progress"))


def test_ajustar_respostas_volta_com_respostas_mantidas(app: AppTest) -> None:
    _preencher(app, MODERADO)
    app.button(key="btn_ajustar").click()
    app.run()
    assert "resultado" not in app.session_state
    assert app.subheader[0].value == "Sobre você"
    assert app.select_slider(key="w_renda_faixa").value == MODERADO["renda_faixa"]


def test_comecar_do_zero_limpa_respostas(app: AppTest) -> None:
    _preencher(app, MODERADO)
    app.button(key="btn_recomecar").click()
    app.run()
    assert app.select_slider(key="w_renda_faixa").value == ui.PERGUNTAS["renda_faixa"].padrao


def test_sem_modelos_mostra_instrucoes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ASSESSOR_MODELS_DIR", str(tmp_path))
    at = AppTest.from_file(APP, default_timeout=30)
    at.run()
    assert any("Modelos não encontrados" in e.value for e in at.error)
    assert "src.segmentation" in at.code[0].value
