"""Etapa 5 — Modelo de recomendação de produtos de investimento.

Formulação: para cada item recomendável (poupança, CDB/depósito, fundos,
ações, previdência), um LightGBM estima P(cliente possui o item | perfil).
O perfil = demografia + os OUTROS itens que o cliente já tem (o próprio item
é excluído das features do seu modelo, para não haver vazamento do alvo).

Avaliação (conjunto de teste, 20%):
    - AUC por item;
    - precision@k e MAP@k ranqueando os 5 itens por probabilidade;
    - Leave-one-out (análogo à competição, que media produtos NOVOS):
      esconde um item que o cliente possui e verifica se o modelo o
      coloca no topo entre os itens que ele "ainda não tem".
Baselines: popularidade dentro do cluster (Etapa 4) e popularidade global.
Explicabilidade: SHAP (TreeExplainer).

Uso:
    python -m src.recommender
"""

from __future__ import annotations

import argparse
import warnings
from pathlib import Path
from typing import Any

import joblib
import lightgbm as lgb
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shap
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.figure import Figure
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split

from src import config
from src.eda import save_fig, set_style
from src.features import add_model_features, add_owned_flags
from src.utils import fmt_num, get_logger

logger = get_logger(__name__)

ITEMS: list[str] = config.RECOMMEND_ITEMS
SEGMENT_CATEGORIES: list[str] = [*config.SEGMENT_MAP.values(), config.UNKNOWN_LABEL]


def _lower_first(label: str) -> str:
    """Minúscula só na 1ª letra e só se não for sigla ("CDB" fica "CDB")."""
    return label if label[:2].isupper() else label[0].lower() + label[1:]


FEATURE_LABELS: dict[str, str] = {
    "age": "Idade",
    "renta_log": "Renda",
    "antiguedad": "Tempo de conta",
    "ind_actividad_cliente": "Cliente ativo",
    "segmento": "Segmento",
    **{f"possui_{i}": f"Já tem {_lower_first(lbl)}" for i, lbl in config.QUESTIONNAIRE_LABELS.items()},
}
# Rótulo quando a flag vale 0: "Já tem X" seria falso
NOT_OWNED_LABELS: dict[str, str] = {
    f"possui_{i}": f"Ainda não tem {_lower_first(lbl)}" for i, lbl in config.QUESTIONNAIRE_LABELS.items()
}
MODEL_NAMES: dict[str, str] = {
    "lgbm": "LightGBM",
    "cluster": "Popular no cluster",
    "global": "Popular global",
}


# ---------------------------------------------------------------------------
# Features
# ---------------------------------------------------------------------------
def prepare(df: pd.DataFrame) -> pd.DataFrame:
    """Adiciona renta_log e flags ``possui_<item>``; segmento como categoria fixa."""
    df = add_owned_flags(add_model_features(df))
    df["segmento"] = pd.Categorical(df["segmento"].astype(str), categories=SEGMENT_CATEGORIES)
    return df


def features_for(item: str) -> list[str]:
    """Features do modelo de ``item``: tudo, menos a flag do próprio item."""
    owned = [f for f in config.REC_OWNED_FEATURES if f != f"possui_{item}"]
    return [*config.REC_NUMERIC_FEATURES, *config.REC_CATEGORICAL_FEATURES, *owned]


def owned_matrix(df: pd.DataFrame) -> np.ndarray:
    """Matriz (n_clientes × n_itens) com 1 onde o cliente possui o item."""
    return df[[f"possui_{i}" for i in ITEMS]].to_numpy(dtype=int)


# ---------------------------------------------------------------------------
# Treino
# ---------------------------------------------------------------------------
def train_models(train: pd.DataFrame, random_state: int) -> dict[str, lgb.LGBMClassifier]:
    """Um LightGBM por item, com early stopping numa validação interna.

    O early stopping usa SÓ a log loss (decisão D19). A AUC estabiliza cedo
    (só mede a ordenação dentro do item) e interromperia o treino com as
    probabilidades ainda presas na taxa média. Para comparar itens
    diferentes no ranking, precisamos de probabilidades calibradas.

    Itens raríssimos (menos de ``MIN_POSITIVES_TO_TRAIN`` clientes que os
    possuem) não recebem modelo (decisão D31): com 4 positivos em 40 mil, o
    LightGBM só decoraria ruído. Para eles, ``score_lgbm`` usa a taxa média.
    A validação interna é estratificada pelo alvo, para que treino e
    validação sempre tenham positivos.
    """
    models: dict[str, lgb.LGBMClassifier] = {}
    for item in ITEMS:
        cols, target = features_for(item), f"possui_{item}"
        n_pos = int(train[target].sum())
        if n_pos < config.MIN_POSITIVES_TO_TRAIN:
            logger.warning("%-12s | só %d clientes possuem: sem modelo, usa a taxa média", item, n_pos)
            continue
        fit_df, valid_df = train_test_split(
            train, test_size=config.VALID_SIZE, stratify=train[target], random_state=random_state
        )
        model = lgb.LGBMClassifier(**config.LGBM_PARAMS, random_state=random_state)
        model.fit(
            fit_df[cols], fit_df[target],
            eval_set=[(valid_df[cols], valid_df[target])],
            eval_metric="binary_logloss",
            callbacks=[lgb.early_stopping(config.EARLY_STOPPING_ROUNDS, first_metric_only=True, verbose=False)],
        )
        models[item] = model
        logger.info("%-12s | posse treino %.2f%% | árvores %d", item, fit_df[target].mean() * 100, model.best_iteration_ or model.n_estimators)
    return models


def popularity_tables(train: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """Baselines: taxa de posse por cluster e taxa global (calculadas no treino)."""
    targets = [f"possui_{i}" for i in ITEMS]
    by_cluster = train.groupby("cluster")[targets].mean()
    by_cluster.columns = ITEMS
    global_rate = train[targets].mean()
    global_rate.index = ITEMS
    return by_cluster, global_rate


# ---------------------------------------------------------------------------
# Scores
# ---------------------------------------------------------------------------
def score_lgbm(models: dict[str, lgb.LGBMClassifier], df: pd.DataFrame, fallback: pd.Series) -> np.ndarray:
    """Probabilidades (n × itens) do LightGBM; item sem modelo recebe a taxa média ``fallback``."""
    return np.column_stack([
        models[i].predict_proba(df[features_for(i)])[:, 1] if i in models else np.full(len(df), float(fallback[i]))
        for i in ITEMS
    ])


def score_cluster(by_cluster: pd.DataFrame, global_rate: pd.Series, df: pd.DataFrame) -> np.ndarray:
    """Taxa de posse do cluster do cliente (fallback global para cluster não visto)."""
    return by_cluster.reindex(df["cluster"]).fillna(global_rate).to_numpy()


def score_global(global_rate: pd.Series, df: pd.DataFrame) -> np.ndarray:
    return np.tile(global_rate.to_numpy(), (len(df), 1))


# ---------------------------------------------------------------------------
# Métricas
# ---------------------------------------------------------------------------
def auc_per_item(y: np.ndarray, scores: np.ndarray) -> pd.Series:
    """AUC de cada item (NaN se o item tem uma única classe no teste)."""
    out = {}
    for j, item in enumerate(ITEMS):
        out[item] = roc_auc_score(y[:, j], scores[:, j]) if len(np.unique(y[:, j])) == 2 else np.nan
    return pd.Series(out)


def precision_map_at_k(y: np.ndarray, scores: np.ndarray, k: int) -> tuple[float, float]:
    """precision@k e MAP@k (definição do Kaggle), só clientes com ≥ 1 item.

    AP@k = Σ_{i≤k} P@i · rel_i / min(nº relevantes, k).
    Com 5 itens, k ≥ 5 equivale a ranquear todos (MAP@7 = MAP@5).
    """
    k = min(k, y.shape[1])
    has_any = y.sum(axis=1) > 0
    y, scores = y[has_any], scores[has_any]
    order = np.argsort(-scores, axis=1, kind="stable")[:, :k]
    rel = np.take_along_axis(y, order, axis=1)
    precision = rel.sum(axis=1) / k
    cum_hits = np.cumsum(rel, axis=1)
    p_at_i = cum_hits / np.arange(1, k + 1)
    ap = (p_at_i * rel).sum(axis=1) / np.minimum(y.sum(axis=1), k)
    return float(precision.mean()), float(ap.mean())


def hide_one_owned(df: pd.DataFrame, random_state: int) -> tuple[pd.DataFrame, np.ndarray, np.ndarray]:
    """Esconde aleatoriamente um item possuído por cliente (leave-one-out).

    Returns:
        (df mascarado, índice do item escondido por linha, máscara de candidatos)
        Candidatos = itens que o cliente "não tem" após esconder um deles.
    """
    y = owned_matrix(df)
    keep = y.sum(axis=1) > 0
    masked, y = df.loc[keep].copy(), y[keep]
    rng = np.random.default_rng(random_state)
    hidden = np.array([rng.choice(np.flatnonzero(row)) for row in y])
    for j, item in enumerate(ITEMS):
        masked.loc[masked.index[hidden == j], f"possui_{item}"] = 0
    candidates = owned_matrix(masked) == 0
    return masked, hidden, candidates


def leave_one_out_metrics(scores: np.ndarray, hidden: np.ndarray, candidates: np.ndarray) -> dict[str, float]:
    """Hit@1, Hit@3 e MRR do item escondido entre os candidatos."""
    s = np.where(candidates, scores, -np.inf)
    hidden_score = s[np.arange(len(s)), hidden]
    rank = 1 + (s > hidden_score[:, None]).sum(axis=1)  # empates favorecem o item escondido
    return {"hit@1": float((rank <= 1).mean()), "hit@3": float((rank <= 3).mean()), "mrr": float((1 / rank).mean())}


def evaluate(scores: dict[str, np.ndarray], loo_scores: dict[str, np.ndarray], y: np.ndarray,
             hidden: np.ndarray, candidates: np.ndarray) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Tabela comparativa de modelos e tabela de AUC por item."""
    rows, aucs = [], {}
    for name in scores:
        auc = auc_per_item(y, scores[name])
        aucs[MODEL_NAMES[name]] = auc
        row: dict[str, Any] = {"modelo": MODEL_NAMES[name], "auc_media": auc.mean()}
        for k in config.EVAL_K:
            p, m = precision_map_at_k(y, scores[name], k)
            row[f"precision@{k}"], row[f"map@{k}"] = p, m
        row.update({f"loo_{k}": v for k, v in leave_one_out_metrics(loo_scores[name], hidden, candidates).items()})
        rows.append(row)
    comparison = pd.DataFrame(rows).set_index("modelo").round(4)
    auc_table = pd.DataFrame(aucs).round(4)
    auc_table.index = [config.QUESTIONNAIRE_LABELS[i] for i in auc_table.index]
    return comparison, auc_table


# ---------------------------------------------------------------------------
# SHAP
# ---------------------------------------------------------------------------
def _shap_values(model: lgb.LGBMClassifier, X: pd.DataFrame) -> np.ndarray:
    """Valores SHAP da classe positiva (compatível com versões que devolvem lista)."""
    with warnings.catch_warnings():  # aviso do shap sobre o formato de saída — tratado abaixo
        warnings.simplefilter("ignore", UserWarning)
        values = shap.TreeExplainer(model).shap_values(X)
    return values[1] if isinstance(values, list) else values


def shap_importance(models: dict[str, lgb.LGBMClassifier], X: pd.DataFrame) -> pd.DataFrame:
    """|SHAP| médio por item × feature (NaN onde a feature não entra no modelo)."""
    table = {}
    for item, model in models.items():
        cols = features_for(item)
        vals = np.abs(_shap_values(model, X[cols])).mean(axis=0)
        table[item] = pd.Series(vals, index=cols)
    out = pd.DataFrame(table).T.reindex(columns=list(FEATURE_LABELS))
    return out.dropna(axis=1, how="all")


def explain(artifact: dict[str, Any], row: pd.DataFrame, item: str, top_n: int = 3) -> list[dict[str, Any]]:
    """Principais fatores (SHAP) que puxam a probabilidade de ``item`` para cima/baixo.

    Usado pelo app para gerar a explicação em linguagem simples. Item sem
    modelo (raro demais, D31) não tem fatores: devolve lista vazia.
    """
    if item not in artifact["models"]:
        return []
    prepared = prepare(row)
    cols = features_for(item)
    vals = _shap_values(artifact["models"][item], prepared[cols])[0]
    order = np.argsort(-np.abs(vals))[:top_n]
    out = []
    for i in order:
        col, valor = cols[i], prepared[cols[i]].iloc[0]
        rotulo = NOT_OWNED_LABELS[col] if col in NOT_OWNED_LABELS and valor == 0 else FEATURE_LABELS[col]
        out.append({"feature": col, "rotulo": rotulo, "valor": valor, "contribuicao": float(vals[i])})
    return out


def predict_proba(artifact: dict[str, Any], rows: pd.DataFrame) -> pd.DataFrame:
    """Probabilidade de posse de cada item recomendável (uso no app)."""
    prepared = prepare(rows)
    scores = score_lgbm(artifact["models"], prepared, artifact["baseline_global"])
    return pd.DataFrame(scores, columns=ITEMS, index=rows.index)


def recommend(artifact: dict[str, Any], rows: pd.DataFrame, k: int = 3) -> list[list[tuple[str, float]]]:
    """Top-k itens que o cliente AINDA NÃO tem, ordenados por probabilidade."""
    proba = predict_proba(artifact, rows)
    owned = owned_matrix(prepare(rows)).astype(bool)
    out = []
    for i, (_, p) in enumerate(proba.iterrows()):
        cands = [(item, float(p[item])) for j, item in enumerate(ITEMS) if not owned[i, j]]
        out.append(sorted(cands, key=lambda t: -t[1])[:k])
    return out


# ---------------------------------------------------------------------------
# Figuras
# ---------------------------------------------------------------------------
def fig_model_comparison(comparison: pd.DataFrame) -> Figure:
    """Barras agrupadas: métricas de ranking por modelo (escala comum 0–1)."""
    metrics = ["auc_media", "precision@1", "map@3", "loo_hit@1", "loo_mrr"]
    labels = ["AUC média", "Precision@1", "MAP@3", "Hit@1 (LOO)", "MRR (LOO)"]
    fig, ax = plt.subplots(figsize=(11, 4))
    width = 0.8 / len(comparison)
    x = np.arange(len(metrics))
    for i, (model, row) in enumerate(comparison.iterrows()):
        pos = x + (i - (len(comparison) - 1) / 2) * width
        ax.bar(pos, row[metrics], width=width * 0.92, color=config.VIZ_CATEGORICAL[i], label=model)
        for xp, v in zip(pos, row[metrics]):
            ax.text(xp, v + 0.015, f"{v:.2f}", ha="center", fontsize=8, color=config.VIZ_TEXT_MUTED)
    ax.set_xticks(x, labels)
    ax.set_ylim(0, 1.08)
    ax.set(title="LightGBM × baselines (conjunto de teste)")
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1))
    ax.grid(axis="x", visible=False)
    fig.tight_layout()
    return fig


def fig_auc_per_item(auc_table: pd.DataFrame) -> Figure:
    """AUC por item: LightGBM × popularidade no cluster."""
    cols = [c for c in auc_table.columns if c != MODEL_NAMES["global"]]  # global = 0,5 por construção
    fig, ax = plt.subplots(figsize=(9, 4))
    width = 0.8 / len(cols)
    x = np.arange(len(auc_table))
    for i, col in enumerate(cols):
        pos = x + (i - (len(cols) - 1) / 2) * width
        ax.bar(pos, auc_table[col], width=width * 0.92, color=config.VIZ_CATEGORICAL[i], label=col)
        for xp, v in zip(pos, auc_table[col]):
            # NaN = item sem positivos suficientes no teste para calcular AUC
            ax.text(xp, 0.41 if np.isnan(v) else v + 0.01, "n/d" if np.isnan(v) else f"{v:.2f}",
                    ha="center", fontsize=8, color=config.VIZ_TEXT_MUTED)
    ax.axhline(0.5, color=config.VIZ_TEXT_MUTED, linestyle="--", linewidth=1)
    ax.text(len(auc_table) - 0.5, 0.51, "acaso (0,5)", ha="right", fontsize=8, color=config.VIZ_TEXT_MUTED)
    ax.set_xticks(x, auc_table.index, rotation=15)
    ax.set_ylim(0.4, 1.05)
    ax.set(title="AUC por item recomendável")
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1))
    ax.grid(axis="x", visible=False)
    fig.tight_layout()
    return fig


def fig_shap_heatmap(importance: pd.DataFrame) -> Figure:
    """Heatmap de |SHAP| médio: o que mais pesa na previsão de cada item."""
    norm = importance.div(importance.max(axis=1), axis=0)  # 1 = feature mais importante do item
    fig, ax = plt.subplots(figsize=(1.0 * importance.shape[1] + 3, 0.6 * importance.shape[0] + 2))
    cmap = LinearSegmentedColormap.from_list("seq", config.VIZ_SEQUENTIAL)
    masked = np.ma.masked_invalid(norm.to_numpy(dtype=float))
    im = ax.imshow(masked, cmap=cmap, vmin=0, vmax=1, aspect="auto")
    for i in range(norm.shape[0]):
        for j in range(norm.shape[1]):
            v = norm.iat[i, j]
            ax.text(j, i, "—" if np.isnan(v) else f"{importance.iat[i, j]:.3f}", ha="center", va="center",
                    fontsize=8, color=config.VIZ_TEXT_MUTED if np.isnan(v) else ("white" if v > 0.6 else config.VIZ_TEXT))
    ax.set_xticks(range(norm.shape[1]), [FEATURE_LABELS[c] for c in norm.columns], rotation=40, ha="right")
    ax.set_yticks(range(norm.shape[0]), [config.QUESTIONNAIRE_LABELS[i] for i in norm.index])
    ax.grid(False)
    ax.set(title="Importância SHAP (|SHAP| médio; cor relativa à feature mais forte do item; — = excluída)")
    fig.colorbar(im, ax=ax, shrink=0.8, label="importância relativa")
    fig.tight_layout()
    return fig


def fig_shap_beeswarm(model: lgb.LGBMClassifier, X: pd.DataFrame, item: str) -> Figure:
    """Beeswarm do SHAP para um item: direção e intensidade de cada feature."""
    cols = features_for(item)
    X_num = X[cols].copy()
    X_num["segmento"] = X_num["segmento"].cat.codes  # o beeswarm precisa de valores numéricos para colorir
    values = _shap_values(model, X[cols])
    plt.figure()
    shap.summary_plot(values, X_num, feature_names=[FEATURE_LABELS[c] for c in cols], show=False, plot_size=(9, 5))
    fig = plt.gcf()
    fig.axes[0].set_title(f"SHAP — {config.QUESTIONNAIRE_LABELS[item]}", loc="left", fontweight="semibold")
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# Relatório e orquestração
# ---------------------------------------------------------------------------
def _md(frame: pd.DataFrame) -> str:
    frame = frame.reset_index()
    head = "| " + " | ".join(map(str, frame.columns)) + " |"
    sep = "|" + "|".join("---" for _ in frame.columns) + "|"
    body = ["| " + " | ".join(f"{v:.3f}" if isinstance(v, float) else str(v) for v in r) + " |" for r in frame.itertuples(index=False)]
    return "\n".join([head, sep, *body])


def build_report(comparison: pd.DataFrame, auc_table: pd.DataFrame, importance: pd.DataFrame,
                 n_train: int, n_test: int, fig_dir: Path, skipped: list[str], beeswarm_item: str) -> str:
    rel = lambda n: (fig_dir / f"{n}.png").as_posix()  # noqa: E731
    imp = importance.rename(index=config.QUESTIONNAIRE_LABELS, columns=FEATURE_LABELS)
    aviso = (
        f"**Sem modelo (menos de {config.MIN_POSITIVES_TO_TRAIN} clientes possuem; usam a taxa média, D31):** "
        + ", ".join(config.QUESTIONNAIRE_LABELS[i] for i in skipped) + "."
        if skipped else "Todos os itens tiveram positivos suficientes para treinar um modelo."
    )
    return "\n\n".join([
        "# Relatório do modelo de recomendação",
        f"Treino: {fmt_num(n_train)} clientes · teste: {fmt_num(n_test)} · itens: {', '.join(config.QUESTIONNAIRE_LABELS[i] for i in ITEMS)}.",
        aviso,
        "## Comparação com baselines",
        _md(comparison),
        "- `precision@k` / `map@k`: ranqueando os 5 itens por probabilidade (clientes com ≥ 1 item). "
        "Com 5 itens, MAP@7 = MAP@5.\n"
        "- `loo_*`: um item possuído é escondido; mede se ele aparece no topo entre os itens que o cliente "
        "\"não tem\". É o cenário real do app.",
        f"![Comparação]({rel('15_comparacao_modelos')})",
        "## AUC por item",
        _md(auc_table),
        f"![AUC]({rel('16_auc_por_item')})",
        "## Explicabilidade (SHAP)",
        _md(imp.round(4)),
        f"![SHAP heatmap]({rel('17_shap_importancia')})",
        f"![SHAP {config.QUESTIONNAIRE_LABELS[beeswarm_item]}]({rel('18_shap_fundos')})",
    ]) + "\n"


def run(input_path: Path, model_path: Path, report_path: Path, fig_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Executa a Etapa 5 completa."""
    rs = config.RANDOM_STATE
    set_style()
    df = prepare(pd.read_parquet(input_path))
    if "cluster" not in df.columns:
        raise ValueError("Base sem coluna 'cluster'. Rode antes: python -m src.segmentation")

    train, test = train_test_split(df, test_size=config.TEST_SIZE, random_state=rs)
    logger.info("Treino %s | teste %s", f"{len(train):,}", f"{len(test):,}")

    models = train_models(train, rs)
    by_cluster, global_rate = popularity_tables(train)

    skipped = [i for i in ITEMS if i not in models]
    if not models:
        raise ValueError("Nenhum item tem positivos suficientes para treinar. Aumente a amostra.")

    y_test = owned_matrix(test)
    scores = {
        "lgbm": score_lgbm(models, test, global_rate),
        "cluster": score_cluster(by_cluster, global_rate, test),
        "global": score_global(global_rate, test),
    }
    masked, hidden, candidates = hide_one_owned(test, rs)
    loo_scores = {
        "lgbm": score_lgbm(models, masked, global_rate),
        "cluster": score_cluster(by_cluster, global_rate, masked),
        "global": score_global(global_rate, masked),
    }
    comparison, auc_table = evaluate(scores, loo_scores, y_test, hidden, candidates)
    logger.info("\n%s", comparison.to_string())

    shap_sample = test.sample(min(config.SHAP_SAMPLE, len(test)), random_state=rs)
    importance = shap_importance(models, shap_sample)

    artifact = {
        "models": models,
        "items": ITEMS,
        "features": {item: features_for(item) for item in ITEMS},
        "baseline_cluster": by_cluster,
        "baseline_global": global_rate,
        "skipped_items": skipped,
        "metrics": comparison,
        "auc_per_item": auc_table,
        "random_state": rs,
    }
    for path in (model_path, report_path):
        path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, model_path)

    save_fig(fig_model_comparison(comparison), "15_comparacao_modelos", fig_dir)
    save_fig(fig_auc_per_item(auc_table), "16_auc_por_item", fig_dir)
    save_fig(fig_shap_heatmap(importance), "17_shap_importancia", fig_dir)
    beeswarm_item = "fundos" if "fundos" in models else next(iter(models))
    save_fig(fig_shap_beeswarm(models[beeswarm_item], shap_sample, beeswarm_item), "18_shap_fundos", fig_dir)
    plt.close("all")

    report = build_report(comparison, auc_table, importance, len(train), len(test), fig_dir, skipped, beeswarm_item)
    report_path.write_text(report, encoding="utf-8")
    logger.info("Salvo: %s | %s", model_path, report_path)
    return comparison, auc_table


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", type=Path, default=config.CLUSTERED_FILE)
    parser.add_argument("--model", type=Path, default=config.REC_MODEL_FILE)
    parser.add_argument("--report", type=Path, default=config.REC_REPORT_FILE)
    parser.add_argument("--fig-dir", type=Path, default=config.FIGURES_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run(args.input, args.model, args.report, args.fig_dir)


if __name__ == "__main__":
    main()
