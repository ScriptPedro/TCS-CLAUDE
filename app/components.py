"""Componentes do app sem dependência do Streamlit (testáveis com pytest).

O ``main.py`` cuida só de layout e navegação; aqui ficam:
    - as perguntas, agrupadas nas 4 etapas do questionário (com faixas, D34);
    - conversão das respostas em ``Questionario`` (faixa → valor representativo);
    - avisos de consistência (não bloqueiam o envio);
    - gráfico de rosca da carteira (Plotly).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import plotly.graph_objects as go

from src import config
from src.portfolio import RESPOSTAS_LEGIVEIS, Questionario

# Cor fixa por classe de ativo (a cor segue a classe; ordem validada para daltonismo)
CLASS_COLORS: dict[str, str] = dict(zip(config.BR_ASSET_CLASSES, config.VIZ_CATEGORICAL))
CLASS_SHORT_LABELS: dict[str, str] = {c: str(info["nome"]) for c, info in config.CLASS_INFO.items()}


# ---------------------------------------------------------------------------
# Perguntas
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Pergunta:
    """Uma pergunta do questionário e como desenhá-la."""

    texto: str
    tipo: str                           # "faixa" (controle deslizante) | "opcao" | "numero" | "multipla"
    opcoes: list[str] = field(default_factory=list)
    rotulos: dict[str, str] = field(default_factory=dict)
    padrao: Any = None
    ajuda: str | None = None
    horizontal: bool = False

    def rotulo(self, chave: str) -> str:
        return self.rotulos.get(chave, chave)


def _legivel(chaves: list[str]) -> dict[str, str]:
    return {k: (t := RESPOSTAS_LEGIVEIS.get(k, k))[0].upper() + t[1:] for k in chaves}


def _faixas(bandas: dict[str, tuple[str, float]]) -> dict[str, str]:
    return {k: rotulo for k, (rotulo, _) in bandas.items()}


PERGUNTAS: dict[str, Pergunta] = {
    # Etapa 1 — Sobre você
    "idade": Pergunta("Qual é a sua idade?", "numero", padrao=30),
    "dependentes": Pergunta(
        "Quantas pessoas dependem da sua renda?", "opcao", config.DEPENDENTS_OPTIONS,
        {"nenhum": "Ninguém", "1_a_2": "1 ou 2", "3_ou_mais": "3 ou mais"}, "nenhum", horizontal=True,
        ajuda="Mais pessoas dependendo de você = menos espaço para perdas.",
    ),
    "estabilidade_renda": Pergunta(
        "Como é a sua renda?", "opcao", list(config.INCOME_STABILITY_RESERVE_MONTHS),
        _legivel(list(config.INCOME_STABILITY_RESERVE_MONTHS)), "estavel",
        ajuda="Renda variável pede uma reserva de emergência maior.",
    ),
    "renda_faixa": Pergunta(
        "Qual é a sua renda mensal líquida?", "faixa", list(config.INCOME_BANDS),
        _faixas(config.INCOME_BANDS), "4000_7000", ajuda="O valor que cai na conta por mês, já com descontos.",
    ),
    # Etapa 2 — Suas finanças
    "cartao_faixa": Pergunta(
        "Quanto da sua renda vai para a fatura do cartão por mês?", "faixa", list(config.CARD_SPEND_BANDS),
        _faixas(config.CARD_SPEND_BANDS), "10_30",
        ajuda=f"Acima de {config.CARD_SPEND_LIMIT:.0%} da renda, um imprevisto pode levar ao rotativo.",
    ),
    "divida_cara": Pergunta(
        "Hoje você paga juros de rotativo do cartão ou de cheque especial?", "opcao", config.EXPENSIVE_DEBT_OPTIONS,
        {"nao": "Não", "sim": "Sim"}, "nao", horizontal=True,
        ajuda="São as dívidas mais caras do Brasil: quitá-las vem antes de investir.",
    ),
    "reserva_faixa": Pergunta(
        "Quanto tempo você conseguiria se manter só com o que tem guardado?", "faixa", list(config.RESERVE_BANDS),
        _faixas(config.RESERVE_BANDS), "nao_tenho",
        ajuda="Conte só o dinheiro que você consegue resgatar rápido (reserva de emergência).",
    ),
    "conta_faixa": Pergunta(
        "Há quanto tempo você tem conta em banco?", "faixa", list(config.ACCOUNT_AGE_BANDS),
        _faixas(config.ACCOUNT_AGE_BANDS), "5_10",
    ),
    # Etapa 3 — Seus objetivos
    "objetivo": Pergunta(
        "Qual é o principal objetivo deste dinheiro?", "opcao", list(config.SUITABILITY_POINTS["objetivo"]),
        _legivel(list(config.SUITABILITY_POINTS["objetivo"])), "reserva",
    ),
    "prazo": Pergunta(
        "Por quanto tempo pretende deixar o dinheiro investido?", "faixa", list(config.SUITABILITY_POINTS["prazo"]),
        _legivel(list(config.SUITABILITY_POINTS["prazo"])), "1_a_3_anos",
    ),
    "necessidade_liquidez": Pergunta(
        "Você pode precisar desse dinheiro antes do prazo?", "opcao", list(config.LIQUIDITY_NEED_BOOST),
        {"nao": "Não, não vou mexer", "talvez": "Talvez", "sim": "Sim, é bem provável"}, "nao", horizontal=True,
        ajuda="Se sim, a carteira guarda uma parte maior em aplicações de resgate rápido.",
    ),
    # Etapa 4 — Você e o risco
    "tolerancia": Pergunta(
        "Se seus investimentos caíssem 20% em um mês, o que você faria?", "opcao",
        list(config.SUITABILITY_POINTS["tolerancia"]),
        {"venderia_tudo": "Venderia tudo para não perder mais", "venderia_parte": "Venderia uma parte",
         "manteria": "Manteria e esperaria recuperar", "compraria_mais": "Aproveitaria para comprar mais"},
        "manteria",
    ),
    "conhecimento": Pergunta(
        "Como você avalia o seu conhecimento sobre investimentos?", "opcao", list(config.KNOWLEDGE_TO_EXPERIENCE),
        {"nenhum": "Nenhum: nunca investi", **{k: v for k, v in _legivel(["basico", "intermediario", "avancado"]).items()}},
        "basico",
    ),
    "produtos": Pergunta(
        "Quais destes produtos você já tem?", "multipla", list(config.QUESTIONNAIRE_ITEMS),
        dict(config.QUESTIONNAIRE_LABELS), ["conta"],
    ),
}

ETAPAS: list[tuple[str, str, list[str]]] = [
    ("Sobre você", "Quem é você e quem depende da sua renda.", ["idade", "dependentes", "estabilidade_renda", "renda_faixa"]),
    ("Suas finanças", "Como está a sua base: cartão, dívidas e reserva.", ["cartao_faixa", "divida_cara", "reserva_faixa", "conta_faixa"]),
    ("Seus objetivos", "Para que é o dinheiro e por quanto tempo.", ["objetivo", "prazo", "necessidade_liquidez"]),
    ("Você e o risco", "Como você lida com oscilações e o que já conhece.", ["tolerancia", "conhecimento", "produtos"]),
]


def respostas_padrao() -> dict[str, Any]:
    """Respostas iniciais do formulário (o padrão de cada pergunta)."""
    return {campo: (list(p.padrao) if isinstance(p.padrao, list) else p.padrao) for campo, p in PERGUNTAS.items()}


# ---------------------------------------------------------------------------
# Respostas → Questionario
# ---------------------------------------------------------------------------
def montar_questionario(respostas: dict[str, Any]) -> tuple[Questionario | None, list[str]]:
    """Converte as faixas em valores representativos e cria o ``Questionario``.

    Ex.: renda "R$ 4.000 a R$ 7.000" → R$ 5.500; cartão "de 10% a 30%" → 20% da renda;
    reserva "de 3 a 6 meses" → 4,5 meses de renda. Os limites das regras (30% no cartão,
    6 ou 12 meses de reserva) coincidem com bordas de faixa, então a escolha da faixa decide
    a regra sem ambiguidade. Erros viram mensagens amigáveis, nunca exceção.
    """
    try:
        renda = config.INCOME_BANDS[respostas["renda_faixa"]][1]
        idade = int(respostas["idade"])
        q = Questionario(
            idade=idade,
            renda_mensal=renda,
            gasto_cartao_mensal=config.CARD_SPEND_BANDS[respostas["cartao_faixa"]][1] * renda,
            reserva_emergencia=config.RESERVE_BANDS[respostas["reserva_faixa"]][1] * renda,
            objetivo=respostas["objetivo"],
            prazo=respostas["prazo"],
            tolerancia=respostas["tolerancia"],
            produtos=frozenset(respostas.get("produtos", [])),
            anos_conta=min(config.ACCOUNT_AGE_BANDS[respostas["conta_faixa"]][1], max(idade - 16, 0)),
            dependentes=respostas["dependentes"],
            estabilidade_renda=respostas["estabilidade_renda"],
            divida_cara=respostas["divida_cara"],
            conhecimento=respostas["conhecimento"],
            necessidade_liquidez=respostas["necessidade_liquidez"],
        )
    except ValueError as exc:
        erros = exc.args[0]
        return None, erros if isinstance(erros, list) else [str(erros)]
    except (TypeError, KeyError) as exc:
        return None, [f"Responda todas as perguntas (faltou: {exc})."]
    return q, []


def avisos_de_consistencia(q: Questionario) -> list[str]:
    """Combinações suspeitas, mas possíveis: o app avisa e segue."""
    avisos = []
    if q.objetivo == "aposentadoria" and q.prazo == "ate_1_ano":
        avisos.append("Aposentadoria com prazo de até 1 ano: confira se o prazo está correto.")
    if q.objetivo == "reserva" and q.prazo in ("3_a_5_anos", "mais_de_5_anos"):
        avisos.append("Reserva de emergência precisa estar disponível a qualquer momento, mesmo com prazo longo.")
    investe = bool(set(q.produtos) & set(config.RECOMMEND_ITEMS))
    if q.tolerancia == "compraria_mais" and not investe:
        avisos.append("Você compraria mais numa queda, mas ainda não tem investimentos. A experiência pesa no perfil.")
    if q.conhecimento in ("intermediario", "avancado") and not investe:
        avisos.append("Você declarou bom conhecimento, mas ainda não tem investimentos: usamos o menor dos dois níveis.")
    return avisos


# ---------------------------------------------------------------------------
# Gráfico e fatores
# ---------------------------------------------------------------------------
def grafico_carteira(alocacao: dict[str, int]) -> go.Figure:
    """Gráfico de rosca da carteira (classes com 0% são omitidas)."""
    classes = [c for c, v in sorted(alocacao.items(), key=lambda kv: -kv[1]) if v > 0]
    fig = go.Figure(
        go.Pie(
            labels=[CLASS_SHORT_LABELS[c] for c in classes],
            values=[alocacao[c] for c in classes],
            hole=0.55,
            sort=False,
            direction="clockwise",
            marker={"colors": [CLASS_COLORS[c] for c in classes], "line": {"color": config.VIZ_SURFACE, "width": 2}},
            texttemplate="%{value}%",
            textposition="outside",
            hovertemplate="%{label}: %{value}%<extra></extra>",
        )
    )
    fig.update_layout(
        showlegend=True,
        legend={"orientation": "h", "y": -0.1, "x": 0.5, "xanchor": "center"},
        margin={"t": 20, "b": 20, "l": 20, "r": 20},
        height=360,
        paper_bgcolor="rgba(0,0,0,0)",
        font={"color": config.VIZ_TEXT, "size": 13},
    )
    return fig


def fatores_legiveis(fatores: list[dict[str, Any]]) -> list[tuple[str, str]]:
    """[(texto, direção)] onde direção é '↑' (puxa para cima) ou '↓' (puxa para baixo)."""
    return [(f["rotulo"], "↑" if f["contribuicao"] > 0 else "↓") for f in fatores]
