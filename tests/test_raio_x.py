"""Testes da referência brasileira (Raio X ANBIMA, D36) e da sua integração com a carteira."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src import config, personas, raio_x
from src import portfolio as pf
from tests.fakes import write_fake_raio_x

ADULTO_MODERADO = personas.PERSONAS["Adulto moderado"]
INVESTIDOR_EXPERIENTE = personas.PERSONAS["Investidor experiente"]
JOVEM_ENDIVIDADO = personas.PERSONAS["Jovem endividado"]


@pytest.fixture(scope="module")
def tabela(tmp_path_factory: pytest.TempPathFactory) -> dict:
    tmp = tmp_path_factory.mktemp("raio_x")
    xlsx = write_fake_raio_x(tmp / "raio_x.xlsx")
    return raio_x.run(xlsx, tmp / "raio_x.json", tmp / "raio_x.md")


def _ref(**posse: float) -> raio_x.ReferenciaBR:
    base = {c: 0.0 for c in config.BR_ASSET_CLASSES}
    return raio_x.ReferenciaBR("de R$ 4.555 a R$ 7.590", "35 a 44 anos", 100, {**base, **posse}, 0.5, "teste")


# ---------------------------------------------------------------------------
# Leitura e tabela
# ---------------------------------------------------------------------------
def test_nao_le_colunas_sensiveis(tmp_path: Path) -> None:
    df = raio_x.ler(write_fake_raio_x(tmp_path / "r.xlsx", n=50))
    assert set(df.columns) == {"nquest", "idade1", "renda", "PESOE", "p9a", "p9b", "p9c"}


def test_preparar_mapeia_codigos_e_multipla_resposta() -> None:
    import pandas as pd
    df = pd.DataFrame({
        "idade1": [20, 40, 70], "renda": [9, 4, 97], "PESOE": [1.0, 1.0, 1.0],
        "p9a": [1, 4, 96], "p9b": [5, 3, 0], "p9c": [0, 0, 0],
    })
    d = raio_x.preparar(df)
    assert d["faixa_renda"].tolist()[:2] == [0, 4] and pd.isna(d["faixa_renda"].iloc[2])
    assert d["faixa_idade"].tolist() == [0, 2, 4]
    assert d.loc[0, ["liquidez", "acoes", "renda_fixa"]].tolist() == [1, 1, 0]
    assert d.loc[1, "renda_fixa"] == 1 and d.loc[1, "algum_investimento"] == 1
    assert d.loc[2, "algum_investimento"] == 0


def test_tabela_formato_e_taxas_validas(tabela: dict) -> None:
    n_r, n_i = len(config.RAIO_X_INCOME_LABELS), len(config.RAIO_X_AGE_LABELS)
    assert len(tabela["celulas"]) == n_r and all(len(linha) == n_i for linha in tabela["celulas"])
    for linha in tabela["celulas"]:
        for cel in linha:
            assert all(0.0 <= cel[c] <= 1.0 for c in raio_x.COLUNAS_TAXA)
    # o sinal sintético aparece: renda mais alta → mais renda fixa
    assert tabela["por_renda"][-1]["renda_fixa"] > tabela["por_renda"][0]["renda_fixa"]
    json.dumps(tabela)  # serializável


def test_celula_vazia_vira_media_da_renda() -> None:
    import pandas as pd
    d = pd.DataFrame({"faixa_renda": [0, 0], "faixa_idade": [0, 0], "peso": [1.0, 1.0],
                      **{c: [1, 0] for c in raio_x.CLASSES}, "algum_investimento": [1, 0]})
    t = raio_x.construir_tabela(d)
    assert t["celulas"][0][4]["n"] == 0
    assert t["celulas"][0][4]["liquidez"] == pytest.approx(t["por_renda"][0]["liquidez"])


@pytest.mark.parametrize(("idade", "renda", "faixa_r", "faixa_i"), [
    (18, 1_000, 0, 0), (25, 1_518, 0, 1), (40, 1_519, 1, 2), (59, 5_500, 3, 3), (60, 15_180, 4, 4), (70, 50_000, 5, 4),
])
def test_referencia_escolhe_a_celula(tabela: dict, idade: int, renda: float, faixa_r: int, faixa_i: int) -> None:
    ref = raio_x.referencia(tabela, idade, renda)
    assert ref.faixa_renda == config.RAIO_X_INCOME_LABELS[faixa_r]
    assert ref.faixa_idade == config.RAIO_X_AGE_LABELS[faixa_i]
    assert ref.n == tabela["celulas"][faixa_r][faixa_i]["n"]


def test_relatorio_gerado(tmp_path: Path) -> None:
    raio_x.run(write_fake_raio_x(tmp_path / "r.xlsx", n=80), tmp_path / "t.json", tmp_path / "r.md")
    texto = (tmp_path / "r.md").read_text(encoding="utf-8")
    assert "Raio X" in texto and "Limitações" in texto and "LGPD" in texto


def test_localizar_aceita_outro_nome(tmp_path: Path) -> None:
    real = write_fake_raio_x(tmp_path / "raio_x_investidor_9.xlsx", n=30)
    assert raio_x.localizar(tmp_path / "DADOS BRUTOS RAIO X 2026.xlsx") == real


def test_localizar_ausente_explica_o_que_fazer(tmp_path: Path) -> None:
    (tmp_path / "raio_x_investidor_9.zip").write_bytes(b"")
    with pytest.raises(FileNotFoundError, match="extraia o .xlsx"):
        raio_x.localizar(tmp_path / "DADOS BRUTOS RAIO X 2026.xlsx")


def test_carregar_ausente_devolve_none(tmp_path: Path) -> None:
    assert raio_x.carregar(tmp_path / "nao_existe.json") is None


# ---------------------------------------------------------------------------
# Integração com a carteira: só muda a posição DENTRO da faixa (D25, D36)
# ---------------------------------------------------------------------------
def test_sem_referencia_afinidade_inalterada() -> None:
    probs = {"poupanca": 0.1, "deposito": 0.4, "fundos": 0.2, "acoes": 0.3, "previdencia": 0.05}
    assert pf.afinidade_por_classe(probs, None) == pf.afinidade_por_classe(probs)


def test_mistura_preserva_a_escala_do_modelo() -> None:
    probs = {"poupanca": 0.1, "deposito": 0.4, "fundos": 0.2, "acoes": 0.3, "previdencia": 0.05}
    misturada = pf.afinidade_por_classe(probs, _ref(liquidez=0.3, renda_fixa=0.2, acoes=0.05))
    assert sum(misturada.values()) == pytest.approx(sum(pf.afinidade_por_classe(probs).values()))
    so_br = pf.afinidade_por_classe(probs, _ref(acoes=0.5), peso_br=1.0)
    assert so_br["acoes"] == pytest.approx(sum(so_br.values()))


@pytest.mark.parametrize("q", [ADULTO_MODERADO, INVESTIDOR_EXPERIENTE, JOVEM_ENDIVIDADO])
def test_referencia_nunca_tira_da_faixa(q: pf.Questionario) -> None:
    for posse in ({"acoes": 0.9}, {"liquidez": 0.9}, {"previdencia": 0.9, "multimercado": 0.9}):
        c = pf.montar_carteira(q, None, _ref(**posse))
        assert sum(c.alocacao.values()) == 100
        for classe, pct in c.alocacao.items():
            lo, hi = c.faixas[classe]
            assert pct == 0 or lo - 1 <= pct <= hi + 1, (classe, pct, c.faixas[classe])


def test_referencia_desloca_dentro_da_faixa() -> None:
    muita_acao = pf.montar_carteira(INVESTIDOR_EXPERIENTE, None, _ref(acoes=0.6, liquidez=0.05))
    pouca_acao = pf.montar_carteira(INVESTIDOR_EXPERIENTE, None, _ref(acoes=0.01, liquidez=0.6))
    assert muita_acao.alocacao["acoes"] > pouca_acao.alocacao["acoes"]
    assert muita_acao.perfil_efetivo == pouca_acao.perfil_efetivo == "arrojado"


def test_personas_continuam_validas_com_referencia(tabela: dict) -> None:
    for nome, q in personas.PERSONAS.items():
        c = pf.montar_carteira(q, None, raio_x.referencia(tabela, q.idade, q.renda_mensal))
        assert [d for d, ok in personas.avaliar(nome, c) if not ok] == [], nome


def test_explicacao_compara_com_brasileiros(tabela: dict) -> None:
    q = ADULTO_MODERADO
    c = pf.montar_carteira(q, None, raio_x.referencia(tabela, q.idade, q.renda_mensal))
    texto = pf.gerar_explicacao(c)
    assert "Como brasileiros parecidos com você investem" in texto
    assert "não o que é adequado" in texto and config.RAIO_X_SOURCE in texto
    assert "Como brasileiros" not in pf.gerar_explicacao(pf.montar_carteira(q))
