"""Orquestrador: questionário → modelos de IA (Etapas 4 e 5) → regras (Etapa 6).

Aqui fica a fronteira explícita entre as duas partes do sistema:
    - ``questionario_para_linha``: traduz as respostas em features do dataset (D16);
    - modelos: cluster (K-Means) e P(item) (LightGBM) + fatores SHAP;
    - ``portfolio``: regras de suitability e carteira (sem ML).

O app (Etapa 7) só precisa chamar ``carregar_artefatos()`` uma vez e
``aconselhar(questionario, artefatos)`` a cada envio do formulário.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from src import config, portfolio, recommender, segmentation
from src.features import items_to_product_row
from src.portfolio import Carteira, Questionario
from src.utils import get_logger

logger = get_logger(__name__)


@dataclass
class Artefatos:
    """Modelos treinados e estatísticas de limpeza carregados do disco."""

    segmentacao: dict[str, Any]
    recomendador: dict[str, Any]
    prep_stats: dict[str, Any]


def carregar_artefatos(
    seg_path: Path = config.SEGMENTATION_MODEL_FILE,
    rec_path: Path = config.REC_MODEL_FILE,
    stats_path: Path = config.PREP_STATS_FILE,
) -> Artefatos:
    """Carrega os três artefatos; mensagem clara se alguma etapa não foi executada."""
    faltando = [p for p in (seg_path, rec_path, stats_path) if not Path(p).exists()]
    if faltando:
        raise FileNotFoundError(
            "Artefatos ausentes: " + ", ".join(map(str, faltando)) +
            ". Rode: prepare_data → segmentation → recommender."
        )
    stats = json.loads(Path(stats_path).read_text(encoding="utf-8"))
    return Artefatos(joblib.load(seg_path), joblib.load(rec_path), stats)


# ---------------------------------------------------------------------------
# Ponte questionário → features
# ---------------------------------------------------------------------------
def quintil_renda_br(renda_mensal: float) -> int:
    """Quintil (0 = mais baixo … 4 = mais alto) da renda mensal brasileira."""
    return int(np.searchsorted(config.BR_MONTHLY_INCOME_EDGES, renda_mensal, side="right"))


def renda_equivalente_eur(renda_mensal: float, prep_stats: dict[str, Any]) -> float:
    """Renda anual espanhola equivalente, pela POSIÇÃO RELATIVA (D3).

    Quem está no 2º quintil de renda no Brasil recebe a renda típica do 2º
    quintil da base espanhola (média geométrica dos limites do quintil,
    adequada à escala log usada pelos modelos).
    """
    q = quintil_renda_br(renda_mensal)
    edges = prep_stats["income_quantile_edges"]
    return math.sqrt(edges[q] * edges[q + 1])


def derivar_segmento(idade: int, quintil: int) -> str:
    """Segmento bancário por regra: universitário (jovem), top (maior quintil) ou particulares."""
    if idade <= config.UNIVERSITY_AGE_MAX:
        return config.SEGMENT_MAP["03 - UNIVERSITARIO"]
    if quintil == config.N_INCOME_QUANTILES - 1:
        return config.SEGMENT_MAP["01 - TOP"]
    return config.SEGMENT_MAP["02 - PARTICULARES"]


def questionario_para_linha(q: Questionario, prep_stats: dict[str, Any]) -> pd.DataFrame:
    """Uma linha no formato do dataset limpo, pronta para os dois modelos."""
    quintil = quintil_renda_br(q.renda_mensal)
    return pd.DataFrame([{
        "age": q.idade,
        "renta": renda_equivalente_eur(q.renda_mensal, prep_stats),
        "antiguedad": round(q.anos_conta * 12),
        "ind_actividad_cliente": config.DEFAULT_ACTIVITY,
        "segmento": derivar_segmento(q.idade, quintil),
        **items_to_product_row(set(q.produtos)),
    }])


# ---------------------------------------------------------------------------
# Resultado
# ---------------------------------------------------------------------------
@dataclass
class Recomendacao:
    """Tudo o que a tela de resultado precisa exibir."""

    questionario: Questionario
    cluster_id: int
    cluster_nome: str
    cluster_descricao: str
    carteira: Carteira
    probabilidades: dict[str, float]
    produtos: list[dict[str, Any]]
    texto: str
    aviso: str = config.DISCLAIMER


def recomendar_produtos(
    linha: pd.DataFrame, artefatos: Artefatos, carteira: Carteira, n: int = config.N_RECOMMENDATIONS
) -> list[dict[str, Any]]:
    """Top-n itens que o usuário não tem, apenas de classes permitidas pela carteira.

    No modo proteção (ações e multimercado zerados), o modelo não pode sugerir
    esses produtos: a regra de negócio prevalece sobre a probabilidade.
    """
    permitidas = carteira.classes_permitidas()
    ranking = recommender.recommend(artefatos.recomendador, linha, k=len(recommender.ITEMS))[0]
    produtos = []
    for item, prob in ranking:
        classe = config.ITEM_TO_BR_CLASS[item]
        if classe not in permitidas or prob < config.MIN_RECOMMEND_PROB:
            continue
        produtos.append({
            "item": item,
            "rotulo": config.QUESTIONNAIRE_LABELS[item],
            "classe_br": config.BR_ASSET_CLASSES[classe],
            "prob": prob,
            "fatores": recommender.explain(artefatos.recomendador, linha, item, top_n=3),
        })
        if len(produtos) == n:
            break
    return produtos


def aconselhar(q: Questionario, artefatos: Artefatos) -> Recomendacao:
    """Fluxo completo do assessor para um questionário."""
    linha = questionario_para_linha(q, artefatos.prep_stats)

    # IA: segmento e afinidade por produto
    cluster_id = int(segmentation.assign_cluster(artefatos.segmentacao, linha)[0])
    info = artefatos.segmentacao["clusters"][cluster_id]
    probs = recommender.predict_proba(artefatos.recomendador, linha).iloc[0].to_dict()

    # Regras: perfil, saúde financeira, carteira
    carteira = portfolio.montar_carteira(q, probs)
    produtos = recomendar_produtos(linha, artefatos, carteira)
    texto = portfolio.gerar_explicacao(carteira, info["nome"], produtos)
    logger.info("Perfil %s | cluster %d (%s) | carteira %s", carteira.perfil_efetivo, cluster_id, info["nome"], carteira.alocacao)
    return Recomendacao(q, cluster_id, info["nome"], info["descricao"], carteira, probs, produtos, texto)
