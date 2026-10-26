"""Testes do motor de suitability e da carteira (Etapa 6) e da ponte do questionário."""

from __future__ import annotations

import numpy as np
import pytest

from src import advisor, config, personas
from src import portfolio as pf
from src.portfolio import Questionario

# ---------------------------------------------------------------------------
# As 3 personas do projeto (definidas uma única vez em src/personas.py)
# ---------------------------------------------------------------------------
JOVEM_ENDIVIDADO = personas.PERSONAS["Jovem endividado"]
ADULTO_MODERADO = personas.PERSONAS["Adulto moderado"]
INVESTIDOR_EXPERIENTE = personas.PERSONAS["Investidor experiente"]


@pytest.mark.parametrize("nome", list(personas.PERSONAS))
def test_personas_atendem_todas_as_expectativas(nome: str) -> None:
    """Saídas esperadas documentadas em src/personas.py (sem modelo: só regras)."""
    carteira = pf.montar_carteira(personas.PERSONAS[nome])
    falhas = [d for d, ok in personas.avaliar(nome, carteira) if not ok]
    assert falhas == [], f"{nome}: {falhas}"


def test_persona_jovem_endividado() -> None:
    c = pf.montar_carteira(JOVEM_ENDIVIDADO)
    assert c.saude.cartao_alto and c.saude.sem_reserva and c.saude.modo_protecao
    assert c.perfil_efetivo == "conservador"
    assert c.alocacao["liquidez"] >= config.PROTECTION_LIQUIDITY_MIN
    assert c.alocacao["acoes"] == c.alocacao["multimercado"] == c.alocacao["previdencia"] == 0
    assert len(c.saude.alertas) == 2


def test_persona_adulto_moderado() -> None:
    c = pf.montar_carteira(ADULTO_MODERADO)
    assert c.perfil.pontos == 8  # prazo 2 + tolerância 2 + objetivo 2 + experiência básica 1 + idade 1
    assert c.perfil_efetivo == "moderado"
    assert not c.saude.modo_protecao and c.saude.alertas == []


def test_persona_investidor_experiente() -> None:
    c = pf.montar_carteira(INVESTIDOR_EXPERIENTE)
    assert c.perfil.pontos == 13 and c.perfil_efetivo == "arrojado"
    lo, hi = config.ALLOCATION_BANDS["arrojado"]["acoes"]
    assert lo <= c.alocacao["acoes"] <= hi
    assert c.alocacao["acoes"] > c.alocacao["liquidez"]


# ---------------------------------------------------------------------------
# Perfil de risco
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("produtos, esperado", [
    (set(), "nenhuma"), ({"conta", "cartao"}, "nenhuma"), ({"poupanca"}, "basica"),
    ({"deposito", "fundos"}, "intermediaria"), ({"acoes"}, "avancada"),
])
def test_experiencia_por_produtos(produtos: set[str], esperado: str) -> None:
    assert pf.experiencia_por_produtos(produtos) == esperado


def test_teto_tolerancia_prevalece_sobre_soma() -> None:
    q = Questionario(**{**INVESTIDOR_EXPERIENTE.__dict__, "tolerancia": "venderia_tudo"})
    perfil = pf.calcular_perfil(q)
    assert perfil.pontos == 10 and perfil.perfil_pela_soma == "moderado"  # a soma diria moderado...
    assert perfil.perfil == "conservador" and perfil.limitado_por


def test_sem_experiencia_limita_a_moderado() -> None:
    q = Questionario(**{**INVESTIDOR_EXPERIENTE.__dict__, "produtos": frozenset({"conta"})})
    assert pf.calcular_perfil(q).perfil == "moderado"


def test_pontuacao_maxima_bate_com_faixas() -> None:
    maximo = sum(max(v.values()) for v in config.SUITABILITY_POINTS.values())
    assert config.RISK_PROFILE_BANDS[-1][1] == maximo
    cobertos = [p for lo, hi, _ in config.RISK_PROFILE_BANDS for p in range(lo, hi + 1)]
    assert cobertos == list(range(maximo + 1))  # sem lacunas nem sobreposição


# ---------------------------------------------------------------------------
# Saúde financeira
# ---------------------------------------------------------------------------
def test_so_cartao_alto_ativa_protecao() -> None:
    q = Questionario(**{**ADULTO_MODERADO.__dict__, "gasto_cartao_mensal": 2_500})  # 42% da renda
    s = pf.avaliar_saude(q)
    assert s.cartao_alto and not s.sem_reserva and s.modo_protecao


def test_reserva_exatamente_no_alvo_nao_ativa() -> None:
    q = Questionario(**{**ADULTO_MODERADO.__dict__, "reserva_emergencia": 6 * 6_000})
    assert not pf.avaliar_saude(q).sem_reserva


# ---------------------------------------------------------------------------
# Alocação
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("perfil", config.RISK_PROFILES)
def test_faixas_do_config_sao_viaveis(perfil: str) -> None:
    pf.validar_faixas({c: tuple(map(float, b)) for c, b in config.ALLOCATION_BANDS[perfil].items()})


@pytest.mark.parametrize("perfil", config.RISK_PROFILES)
@pytest.mark.parametrize("seed", range(20))
def test_alocacao_soma_100_e_respeita_faixas(perfil: str, seed: int) -> None:
    rng = np.random.default_rng(seed)
    faixas = {c: tuple(map(float, b)) for c, b in config.ALLOCATION_BANDS[perfil].items()}
    afinidade = {c: float(rng.random()) for c in faixas}
    aloc = pf.alocar(faixas, afinidade)
    assert sum(aloc.values()) == 100
    for c, (lo, hi) in faixas.items():
        assert lo <= aloc[c] <= hi, (c, aloc[c], lo, hi)


def test_maior_afinidade_recebe_mais_peso() -> None:
    faixas = {c: tuple(map(float, b)) for c, b in config.ALLOCATION_BANDS["moderado"].items()}
    base = {c: 0.2 for c in faixas}
    alta = {**base, "acoes": 0.9}
    assert pf.alocar(faixas, alta)["acoes"] > pf.alocar(faixas, base)["acoes"]


def test_mapeamento_item_classe_completo() -> None:
    assert set(config.ITEM_TO_BR_CLASS) == set(config.RECOMMEND_ITEMS)
    assert set(config.ITEM_TO_BR_CLASS.values()) <= set(config.BR_ASSET_CLASSES)
    assert set(config.BR_ASSET_CLASSES) == set(config.ALLOCATION_BANDS["moderado"])


def test_faixas_inviaveis_sao_rejeitadas() -> None:
    with pytest.raises(ValueError):
        pf.validar_faixas({"a": (60, 70), "b": (50, 60)})


# ---------------------------------------------------------------------------
# Validação e explicação
# ---------------------------------------------------------------------------
def test_validacao_lista_todos_os_erros() -> None:
    with pytest.raises(ValueError) as exc:
        Questionario(idade=15, renda_mensal=0, gasto_cartao_mensal=-1, reserva_emergencia=0,
                     objetivo="ficar_rico", prazo="1_a_3_anos", tolerancia="manteria")
    erros = exc.value.args[0]
    assert len(erros) == 4  # idade, renda, cartão negativo, objetivo inválido


def test_explicacao_tem_aviso_e_alertas() -> None:
    texto = pf.gerar_explicacao(pf.montar_carteira(JOVEM_ENDIVIDADO), cluster_nome="Jovem só conta")
    assert config.DISCLAIMER in texto
    assert "cartão" in texto and "reserva" in texto and "Jovem só conta" in texto


# ---------------------------------------------------------------------------
# Ponte questionário → features (advisor)
# ---------------------------------------------------------------------------
STATS = {"income_quantile_edges": [10_000.0, 40_000.0, 60_000.0, 80_000.0, 120_000.0, 500_000.0]}


@pytest.mark.parametrize("renda, quintil", [(1_000, 0), (1_500, 1), (3_000, 2), (5_000, 3), (50_000, 4)])
def test_quintil_renda_br(renda: float, quintil: int) -> None:
    assert advisor.quintil_renda_br(renda) == quintil


def test_renda_equivalente_cresce_com_renda_br() -> None:
    valores = [advisor.renda_equivalente_eur(r, STATS) for r in (1_000, 2_000, 3_000, 5_000, 10_000)]
    assert valores == sorted(valores) and len(set(valores)) == 5


def test_linha_do_questionario() -> None:
    linha = advisor.questionario_para_linha(ADULTO_MODERADO, STATS)
    assert linha.loc[0, "segmento"] == "particulares"
    assert linha.loc[0, "antiguedad"] == 180
    assert linha.loc[0, "ind_ahor_fin_ult1"] == 1 and linha.loc[0, "ind_fond_fin_ult1"] == 0
    assert advisor.questionario_para_linha(JOVEM_ENDIVIDADO, STATS).loc[0, "segmento"] == "universitario"


@pytest.mark.parametrize("perfil", config.RISK_PROFILES)
@pytest.mark.parametrize("seed", range(20))
def test_sem_residuos_respeita_faixas_e_minimo(perfil: str, seed: int) -> None:
    rng = np.random.default_rng(100 + seed)
    faixas = {c: tuple(map(float, b)) for c, b in config.ALLOCATION_BANDS[perfil].items()}
    aloc = pf.alocar_sem_residuos(faixas, {c: float(rng.random()) ** 3 for c in faixas})
    assert sum(aloc.values()) == 100
    for c, (lo, hi) in faixas.items():
        assert lo <= aloc[c] <= hi
        if lo == 0:  # classe opcional: ou fica de fora, ou tem fatia relevante
            assert aloc[c] == 0 or aloc[c] >= config.MIN_ALLOCATION_PCT


def test_numeros_no_padrao_brasileiro() -> None:
    from src.utils import fmt_brl, fmt_num
    assert fmt_brl(30_000) == "R$ 30.000" and fmt_num(1_234_567.891, 2) == "1.234.567,89"
    alerta = pf.avaliar_saude(JOVEM_ENDIVIDADO).alertas[1]
    assert "0,2 meses" in alerta and "R$ 11.500" in alerta


# ---------------------------------------------------------------------------
# Perguntas de refinamento (D33)
# ---------------------------------------------------------------------------
def _com(q: Questionario, **mudancas: object) -> Questionario:
    return Questionario(**{**q.__dict__, **mudancas})


def test_tres_dependentes_limitam_a_moderado() -> None:
    perfil = pf.calcular_perfil(_com(INVESTIDOR_EXPERIENTE, dependentes="3_ou_mais"))
    assert perfil.perfil_pela_soma == "arrojado" and perfil.perfil == "moderado"
    assert any("dependentes" in m for m in perfil.limitado_por)


def test_renda_variavel_exige_reserva_de_12_meses() -> None:
    # Adulto moderado tem ~6,7 meses de reserva: suficiente com renda estável, insuficiente com renda variável
    assert not pf.avaliar_saude(ADULTO_MODERADO).sem_reserva
    saude = pf.avaliar_saude(_com(ADULTO_MODERADO, estabilidade_renda="variavel"))
    assert saude.sem_reserva and saude.meses_alvo == 12 and saude.modo_protecao
    assert "sua renda varia" in saude.alertas[-1]


def test_divida_cara_ativa_protecao_mesmo_com_reserva() -> None:
    carteira = pf.montar_carteira(_com(INVESTIDOR_EXPERIENTE, divida_cara="sim"))
    assert carteira.saude.modo_protecao and not carteira.saude.sem_reserva
    assert carteira.alocacao["acoes"] == 0
    assert "rotativo" in pf.proximos_passos(carteira)[0]


@pytest.mark.parametrize("declarado, esperado", [
    (None, "avancada"), ("avancado", "avancada"), ("basico", "basica"), ("nenhum", "nenhuma"),
])
def test_experiencia_efetiva_e_o_menor_nivel(declarado: str | None, esperado: str) -> None:
    assert pf.experiencia_efetiva(_com(INVESTIDOR_EXPERIENTE, conhecimento=declarado)) == esperado


def test_conhecimento_alto_nao_supera_produtos() -> None:
    q = _com(JOVEM_ENDIVIDADO, conhecimento="avancado")  # só tem conta e cartão
    assert pf.experiencia_efetiva(q) == "nenhuma"


@pytest.mark.parametrize("necessidade, extra", [("nao", 0), ("talvez", 10), ("sim", 20)])
def test_necessidade_de_liquidez_sobe_o_minimo(necessidade: str, extra: int) -> None:
    carteira = pf.montar_carteira(_com(ADULTO_MODERADO, necessidade_liquidez=necessidade))
    base = config.ALLOCATION_BANDS["moderado"]["liquidez"][0]
    assert carteira.faixas["liquidez"][0] == base + extra
    assert carteira.alocacao["liquidez"] >= base + extra and sum(carteira.alocacao.values()) == 100


@pytest.mark.parametrize("necessidade", list(config.LIQUIDITY_NEED_BOOST))
@pytest.mark.parametrize("persona", list(personas.PERSONAS))
def test_faixas_continuam_viaveis_com_reforco_de_liquidez(persona: str, necessidade: str) -> None:
    """Pior caso: modo proteção (mín. 60%) + 20 pontos extras ainda soma 100%."""
    carteira = pf.montar_carteira(_com(personas.PERSONAS[persona], necessidade_liquidez=necessidade))
    pf.validar_faixas(carteira.faixas)
    assert sum(carteira.alocacao.values()) == 100


def test_resposta_de_refinamento_invalida() -> None:
    with pytest.raises(ValueError):
        _com(ADULTO_MODERADO, dependentes="muitos")


# ---------------------------------------------------------------------------
# Leitura da carteira em linguagem simples (D35)
# ---------------------------------------------------------------------------
def test_risco_da_carteira_cresce_com_o_perfil() -> None:
    notas = [pf.risco_carteira(pf.montar_carteira(personas.PERSONAS[n]))[0] for n in personas.PERSONAS]
    assert notas == sorted(notas)
    assert pf.risco_carteira(pf.montar_carteira(JOVEM_ENDIVIDADO))[1] == "Baixo"


def test_resumo_tem_tres_frases_e_cita_a_prioridade() -> None:
    resumo = pf.resumo_simples(pf.montar_carteira(JOVEM_ENDIVIDADO))
    assert len(resumo) == 3
    assert "organizar a base" in resumo[1] and "R$ 11.500" in resumo[1]
    assert "base financeira está em ordem" in pf.resumo_simples(pf.montar_carteira(ADULTO_MODERADO))[1]


def test_explicar_classe_cobre_todos_os_casos() -> None:
    protegida = pf.montar_carteira(JOVEM_ENDIVIDADO)
    assert "organizar a base" in pf.explicar_classe(protegida, "acoes")
    assert "entre 60% e 100%" in pf.explicar_classe(protegida, "liquidez")
    com_extra = pf.montar_carteira(_com(ADULTO_MODERADO, necessidade_liquidez="sim"))
    assert "subiu 20 pontos" in pf.explicar_classe(com_extra, "liquidez")


def test_por_mil() -> None:
    assert pf.por_mil(25) == 250


def test_proximos_passos_sem_protecao_falam_de_rebalancear() -> None:
    passos = pf.proximos_passos(pf.montar_carteira(ADULTO_MODERADO))
    assert any("6 a 12 meses" in p for p in passos)
    assert not any("rotativo" in p for p in passos)


@pytest.mark.parametrize("perfil, teto", [("conservador", "Baixo"), ("moderado", "Moderado")])
def test_rotulo_de_risco_nunca_fica_acima_do_perfil(perfil: str, teto: str) -> None:
    """Para QUALQUER carteira possível do perfil (afinidades aleatórias e reforço de liquidez).

    Ficar abaixo é legítimo (moderado com muita liquidez tem risco baixo); acima, nunca.
    """
    ordem = [r for _, r in config.PORTFOLIO_RISK_BANDS]
    rng = np.random.default_rng(7)
    for extra in config.LIQUIDITY_NEED_BOOST.values():
        faixas = {c: tuple(map(float, b)) for c, b in config.ALLOCATION_BANDS[perfil].items()}
        lo, hi = faixas["liquidez"]
        faixas["liquidez"] = (lo + extra, max(hi, lo + extra))
        for _ in range(50):
            aloc = pf.alocar(faixas, {c: float(rng.random()) for c in faixas})
            carteira = pf.Carteira(None, None, perfil, faixas, {}, aloc)
            assert ordem.index(pf.risco_carteira(carteira)[1]) <= ordem.index(teto), aloc
