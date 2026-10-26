"""Etapa 8 — Auditoria de viés.

``sexo`` NÃO é feature de nenhum modelo (decisão D11). Mesmo assim, os modelos
podem tratar grupos de forma diferente por PROXIES (renda, idade, segmento)
ou por reproduzir diferenças históricas de posse de produtos. Esta auditoria
mede isso:

1. Distribuição dos clusters por sexo (+ V de Cramér: 0 = independente, 1 = determinado).
2. Probabilidade média prevista de cada item por sexo e razão de impacto
   (menor média / maior média). Abaixo de 0,8 = alerta (regra dos 4/5,
   referência usual em auditorias de discriminação).
3. O mesmo por faixa etária, só para transparência: idade é critério
   LEGÍTIMO de suitability (horizonte de investimento), então não gera alerta.

Uso:
    python -m src.bias_audit
"""

from __future__ import annotations

import argparse
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from scipy.stats import chi2_contingency

from src import config, recommender
from src.utils import fmt_num, get_logger

logger = get_logger(__name__)

DISPARITY_THRESHOLD: float = 0.8   # regra dos 4/5
PROTECTED: str = "sexo"


def cramers_v(a: pd.Series, b: pd.Series) -> float:
    """Associação entre duas variáveis categóricas (0 a 1)."""
    table = pd.crosstab(a, b)
    if min(table.shape) < 2:
        return 0.0
    chi2 = chi2_contingency(table, correction=False)[0]
    n = table.to_numpy().sum()
    return float(np.sqrt(chi2 / (n * (min(table.shape) - 1))))


def cluster_by_group(df: pd.DataFrame, group: str) -> pd.DataFrame:
    """% de cada grupo em cada cluster (colunas somam 100)."""
    return (pd.crosstab(df["cluster_nome"], df[group], normalize="columns") * 100).round(1)


def probability_by_group(proba: pd.DataFrame, groups: pd.Series) -> pd.DataFrame:
    """P média prevista por item × grupo, com razão de impacto (mín/máx)."""
    table = proba.groupby(groups.values).mean().T
    table.index = pd.Index([config.QUESTIONNAIRE_LABELS[i] for i in table.index], name="item")
    table["razao_impacto"] = table.min(axis=1) / table.max(axis=1)
    return table.round(3)


def ratio_within_strata(proba: pd.DataFrame, groups: pd.Series, strata: pd.Series) -> pd.DataFrame:
    """Razão de impacto entre ``groups`` calculada DENTRO de cada estrato (ex.: faixa etária).

    Se a disparidade geral some dentro dos estratos, ela é explicada pela
    variável de estratificação (ex.: um grupo é mais jovem), não pelo grupo em si.
    """
    d = proba.assign(_g=groups.values, _s=strata.values)
    means = d.groupby(["_s", "_g"], observed=True)[list(proba.columns)].mean().unstack("_g")
    ratios = pd.DataFrame({i: means[i].min(axis=1) / means[i].max(axis=1) for i in proba.columns})
    ratios.columns = [config.QUESTIONNAIRE_LABELS[i] for i in ratios.columns]
    ratios.index.name = strata.name or "estrato"
    return ratios.round(2)


def audit(df: pd.DataFrame, rec_artifact: dict) -> dict[str, object]:
    """Executa a auditoria e devolve tabelas e alertas."""
    known = df[df[PROTECTED] != config.UNKNOWN_LABEL]  # "desconhecido" não é grupo comparável
    proba = recommender.predict_proba(rec_artifact, known)

    by_sex = probability_by_group(proba, known[PROTECTED])
    by_age = probability_by_group(proba, known["faixa_etaria"].astype(str))
    alerts = [
        f"{item}: razão de impacto {r:.2f} < {DISPARITY_THRESHOLD}"
        for item, r in by_sex["razao_impacto"].items() if r < DISPARITY_THRESHOLD
    ]
    within_age = ratio_within_strata(proba, known[PROTECTED], known["faixa_etaria"].astype(str).rename("faixa_etaria"))
    residual = [
        f"{item} em {faixa}: {r:.2f}"
        for faixa, row in within_age.iterrows() for item, r in row.items() if r < DISPARITY_THRESHOLD
    ]
    return {
        "n": len(known),
        "idade_media_por_sexo": known.groupby(PROTECTED)["age"].mean().round(1).to_dict(),
        "within_age": within_age,
        "residual_alerts": residual,
        "cramers_v_cluster_sexo": cramers_v(known["cluster_nome"], known[PROTECTED]),
        "cramers_v_cluster_idade": cramers_v(known["cluster_nome"], known["faixa_etaria"].astype(str)),
        "cluster_by_sex": cluster_by_group(known, PROTECTED),
        "proba_by_sex": by_sex,
        "proba_by_age": by_age,
        "alerts": alerts,
    }


def _md(frame: pd.DataFrame) -> str:
    frame = frame.reset_index()
    head = "| " + " | ".join(map(str, frame.columns)) + " |"
    sep = "|" + "|".join("---" for _ in frame.columns) + "|"
    body = ["| " + " | ".join(str(v) for v in r) + " |" for r in frame.itertuples(index=False)]
    return "\n".join([head, sep, *body])


def build_report(res: dict[str, object]) -> str:
    alerts = res["alerts"]
    status = (
        "✅ Nenhum item com razão de impacto abaixo de 0,8 entre os sexos."
        if not alerts else "⚠️ Itens com disparidade relevante entre os sexos:\n" + "\n".join(f"- {a}" for a in alerts)
    )
    return "\n\n".join([
        "# Auditoria de viés",
        f"Base auditada: {fmt_num(res['n'])} clientes com sexo informado. `sexo` não é feature de nenhum modelo (D11): "
        "diferenças abaixo vêm de proxies (renda, idade, segmento) ou de padrões históricos de posse.",
        "## Resumo",
        status,
        f"- V de Cramér cluster × sexo: **{res['cramers_v_cluster_sexo']:.3f}** "
        f"(cluster × faixa etária: {res['cramers_v_cluster_idade']:.3f}, para comparação).",
        "## Clusters por sexo (% de cada grupo em cada cluster)",
        _md(res["cluster_by_sex"]),
        "## Probabilidade média prevista por sexo",
        "`razao_impacto` = menor média ÷ maior média. Abaixo de 0,8 → alerta (regra dos 4/5).",
        _md(res["proba_by_sex"]),
        "## Controlando pela idade: razão de impacto DENTRO de cada faixa etária",
        "Idade média por sexo: " + " · ".join(f"{g} {fmt_num(v, 1)} anos" for g, v in res["idade_media_por_sexo"].items())
        + ". Se a razão volta a ficar ≥ 0,8 dentro das faixas, a disparidade geral é explicada pela diferença de "
        "idade entre os grupos (proxy), não pelo sexo em si.",
        _md(res["within_age"]),
        ("Disparidades residuais (< 0,8 mesmo dentro da faixa): " + "; ".join(res["residual_alerts"]) + "."
         if res["residual_alerts"] else "Nenhuma disparidade residual dentro das faixas etárias."),
        "## Probabilidade média prevista por faixa etária (transparência)",
        "Idade é critério legítimo de suitability (horizonte de investimento); não gera alerta.",
        _md(res["proba_by_age"]),
        "## Como interpretar",
        "- Disparidade **não prova discriminação**: pode refletir diferenças reais de renda entre os grupos na base "
        "espanhola de 2016. Também **não prova ausência**: a base reflete as vendas do banco, não a adequação.\n"
        "- Mitigação disponível: as recomendações finais passam pelo motor de suitability, que usa apenas "
        "respostas do próprio usuário (prazo, tolerância, objetivo, reserva). Isso limita o efeito do modelo "
        "a ajustes DENTRO das faixas do perfil.",
    ]) + "\n"


def run(clustered_path: Path, rec_model_path: Path, report_path: Path) -> dict[str, object]:
    df = pd.read_parquet(clustered_path)
    if PROTECTED not in df.columns:
        raise ValueError(f"Coluna '{PROTECTED}' ausente na base clusterizada.")
    res = audit(df, joblib.load(rec_model_path))
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(build_report(res), encoding="utf-8")
    logger.info("Auditoria: %d alerta(s). Relatório: %s", len(res["alerts"]), report_path)
    return res


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", type=Path, default=config.CLUSTERED_FILE)
    parser.add_argument("--model", type=Path, default=config.REC_MODEL_FILE)
    parser.add_argument("--report", type=Path, default=config.REPORTS_DIR / "auditoria_vies.md")
    args = parser.parse_args()
    run(args.input, args.model, args.report)


if __name__ == "__main__":
    main()
