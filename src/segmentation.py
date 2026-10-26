"""Etapa 4 — Segmentação de clientes (núcleo de IA não supervisionada).

Fluxo:
    1. Features: idade, log(renda), antiguidade, atividade, segmento (one-hot)
       e contagem de produtos por classe.
    2. Padronização (StandardScaler) + One-Hot num ColumnTransformer.
    3. Avaliação de k = 2..10: inércia (cotovelo), silhouette, Davies-Bouldin,
       Calinski-Harabasz e BIC do GMM.
    4. Escolha de k: maior silhouette dentro da faixa de negócio [4, 8].
    5. K-Means final + comparação com Gaussian Mixture (GMM) no mesmo k.
    6. Teste de estabilidade (bootstrap + Adjusted Rand Index).
    7. Perfil, nome e descrição automáticos de cada cluster.
    8. Salva o pipeline (joblib), a base com o cluster, figuras e relatório.

Uso:
    python -m src.segmentation
    python -m src.segmentation --k 6     # força um k específico
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.figure import Figure
from sklearn.cluster import KMeans
from sklearn.compose import ColumnTransformer
from sklearn.decomposition import PCA
from sklearn.metrics import (
    adjusted_rand_score,
    calinski_harabasz_score,
    davies_bouldin_score,
    silhouette_score,
)
from sklearn.mixture import GaussianMixture
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import MinMaxScaler, OneHotEncoder, StandardScaler

from src import config
from src.eda import save_fig, set_style
from src.features import add_model_features
from src.utils import fmt_num, get_logger

logger = get_logger(__name__)

# Colunas usadas para descrever (não para treinar) os clusters
PROFILE_COLUMNS: dict[str, str] = {
    "age": "Idade",
    "renta_log": "Renda (log)",
    "antiguedad": "Antiguidade (meses)",
    "ind_actividad_cliente": "Ativo",
    "n_produtos": "Nº produtos",
    "possui_investimento": "Investe",
    **{f"n_{g}": f"Nº {config.GROUP_LABELS[g].lower()}" for g in config.PRODUCT_GROUPS},
}


# ---------------------------------------------------------------------------
# 1–2. Features e pré-processamento
# ---------------------------------------------------------------------------
def prepare_features(df: pd.DataFrame) -> pd.DataFrame:
    """Garante as colunas de features (renta_log, n_<classe>) e tipos simples."""
    df = add_model_features(df)
    for col in config.SEG_CATEGORICAL_FEATURES:
        df[col] = df[col].astype(str)
    return df


def build_preprocessor() -> ColumnTransformer:
    """Escala cada tipo de variável de forma adequada (decisão D14).

    - Contínuas (idade, log renda, antiguidade): StandardScaler. Sem isso, a
      antiguidade (0–250 meses) dominaria a distância euclidiana.
    - Binárias e contagens (atividade, n_<classe>): MinMax 0–1. Padronizar
      uma variável binária rara (ex.: previdência, ~1%) coloca quem a possui
      a ~10 desvios-padrão da média, e o K-Means cria um cluster só para ela.
    - segmento: one-hot (0/1).
    """
    return ColumnTransformer(
        [
            ("cont", StandardScaler(), config.SEG_CONTINUOUS_FEATURES),
            ("bound", MinMaxScaler(), config.SEG_BOUNDED_FEATURES),
            (
                "cat",
                OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                config.SEG_CATEGORICAL_FEATURES,
            ),
        ]
    )


def _sample_index(n: int, size: int, random_state: int) -> np.ndarray:
    rng = np.random.default_rng(random_state)
    return rng.choice(n, size=min(size, n), replace=False)


# ---------------------------------------------------------------------------
# 3–4. Escolha de k
# ---------------------------------------------------------------------------
def evaluate_k(X: np.ndarray, k_range: range, random_state: int) -> pd.DataFrame:
    """Calcula as métricas de qualidade de cluster para cada k."""
    idx = _sample_index(len(X), config.SILHOUETTE_SAMPLE, random_state)
    rows = []
    for k in k_range:
        km = KMeans(n_clusters=k, n_init=config.KMEANS_N_INIT, random_state=random_state).fit(X)
        gmm = GaussianMixture(
            n_components=k, covariance_type="full", reg_covar=config.GMM_REG_COVAR, random_state=random_state
        ).fit(X)
        rows.append(
            {
                "k": k,
                "inercia": km.inertia_,
                "silhouette": silhouette_score(X[idx], km.labels_[idx]),
                "davies_bouldin": davies_bouldin_score(X, km.labels_),
                "calinski_harabasz": calinski_harabasz_score(X, km.labels_),
                "gmm_bic": gmm.bic(X),
            }
        )
        logger.info("k=%d | silhouette=%.3f | DB=%.3f", k, rows[-1]["silhouette"], rows[-1]["davies_bouldin"])
    return pd.DataFrame(rows).set_index("k")


def elbow_k(metrics: pd.DataFrame) -> int:
    """Cotovelo pelo método da maior distância à reta (kneedle simplificado).

    Normaliza k e inércia em [0, 1] e pega o ponto mais distante da reta
    que liga o primeiro ao último k.
    """
    k = metrics.index.to_numpy(dtype=float)
    y = metrics["inercia"].to_numpy(dtype=float)
    kn = (k - k.min()) / (k.max() - k.min())
    yn = (y - y.min()) / (y.max() - y.min())
    distance = np.abs(kn + yn - 1) / np.sqrt(2)  # reta de (0,1) a (1,0)
    return int(k[np.argmax(distance)])


def choose_k(metrics: pd.DataFrame, k_min: int, k_max: int) -> int:
    """Maior silhouette dentro da faixa de negócio [k_min, k_max]."""
    window = metrics.loc[(metrics.index >= k_min) & (metrics.index <= k_max)]
    if window.empty:
        raise ValueError(f"Nenhum k avaliado dentro de [{k_min}, {k_max}]")
    return int(window["silhouette"].idxmax())


# ---------------------------------------------------------------------------
# 5–6. Modelos finais, comparação e estabilidade
# ---------------------------------------------------------------------------
def fit_kmeans(X: np.ndarray, k: int, random_state: int) -> KMeans:
    return KMeans(n_clusters=k, n_init=config.KMEANS_N_INIT, random_state=random_state).fit(X)


def fit_gmm(X: np.ndarray, k: int, random_state: int) -> GaussianMixture:
    return GaussianMixture(
        n_components=k, covariance_type="full", reg_covar=config.GMM_REG_COVAR, random_state=random_state
    ).fit(X)


def compare_models(X: np.ndarray, labels: dict[str, np.ndarray], random_state: int) -> pd.DataFrame:
    """Mesmas métricas para cada modelo + concordância entre eles (ARI)."""
    idx = _sample_index(len(X), config.SILHOUETTE_SAMPLE, random_state)
    rows = []
    for name, lab in labels.items():
        n_clusters = len(np.unique(lab))
        rows.append(
            {
                "modelo": name,
                "clusters": n_clusters,
                "silhouette": silhouette_score(X[idx], lab[idx]) if n_clusters > 1 else np.nan,
                "davies_bouldin": davies_bouldin_score(X, lab) if n_clusters > 1 else np.nan,
                "menor_cluster_pct": np.bincount(lab).min() / len(lab) * 100,
            }
        )
    table = pd.DataFrame(rows).set_index("modelo").round(3)
    names = list(labels)
    if len(names) == 2:
        ari = adjusted_rand_score(labels[names[0]], labels[names[1]])
        table.attrs["ari_entre_modelos"] = round(float(ari), 3)
    return table


def stability(X: np.ndarray, k: int, random_state: int) -> list[float]:
    """Treina em subamostras (80%) e compara com o modelo de referência (ARI).

    ARI = 1: mesmas partições; ARI ≈ 0: concordância de acaso.
    Clusters estáveis indicam estrutura real nos dados, não ruído do algoritmo.
    """
    reference = fit_kmeans(X, k, random_state).labels_
    scores = []
    for i in range(config.STABILITY_RUNS):
        idx = _sample_index(len(X), int(len(X) * config.STABILITY_FRACTION), random_state + i + 1)
        km = fit_kmeans(X[idx], k, random_state + i + 1)
        scores.append(round(float(adjusted_rand_score(reference, km.predict(X))), 3))
    logger.info("Estabilidade (ARI): %s", scores)
    return scores


# ---------------------------------------------------------------------------
# 7. Perfil e nomes
# ---------------------------------------------------------------------------
def relabel_by_size(labels: np.ndarray) -> dict[int, int]:
    """Mapa rótulo original → novo rótulo, com o cluster 0 sendo o maior.

    Os números do K-Means são arbitrários; ordenar por tamanho deixa
    figuras e relatórios estáveis e fáceis de ler.
    """
    order = pd.Series(labels).value_counts().index
    return {int(old): new for new, old in enumerate(order)}


def profile_clusters(df: pd.DataFrame, labels: np.ndarray) -> pd.DataFrame:
    """Tabela de perfil (uma linha por cluster) em unidades de negócio."""
    d = df.assign(cluster=labels)
    g = d.groupby("cluster")
    profile = pd.DataFrame(
        {
            "tamanho_pct": g.size() / len(d) * 100,
            "idade_media": g["age"].mean(),
            "renda_mediana_eur": g["renta"].median(),
            "antiguidade_anos": g["antiguedad"].mean() / 12,
            "pct_ativos": g["ind_actividad_cliente"].mean() * 100,
            "n_produtos_medio": g["n_produtos"].mean(),
            "pct_investe": g["possui_investimento"].mean() * 100,
            **{f"pct_{grp}": g[f"n_{grp}"].apply(lambda s: (s > 0).mean() * 100) for grp in config.PRODUCT_GROUPS},
        }
    )
    seg_share = pd.crosstab(d["cluster"], d["segmento"], normalize="index")
    profile["segmento_predominante"] = seg_share.idxmax(axis=1)
    profile["pct_segmento_predominante"] = seg_share.max(axis=1) * 100
    return profile.round(2)


def _global_profile(df: pd.DataFrame) -> pd.Series:
    return profile_clusters(df, np.zeros(len(df), dtype=int)).iloc[0]


def _age_label(age: float) -> str:
    if age < 30:
        return "Jovem"
    if age < 50:
        return "Adulto"
    if age < 65:
        return "Maduro"
    return "Sênior"


def _trait(row: pd.Series, glob: pd.Series) -> str:
    """Traço dominante do cluster, comparado com a média da base.

    A ordem das regras é a prioridade: o que mais diferencia o cluster para
    um assessor de investimentos (já investe?) vem primeiro.
    """
    if row["pct_investe"] >= 1.5 * glob["pct_investe"] and row["pct_investe"] >= 10:
        return "investidor"
    if row["renda_mediana_eur"] >= 1.3 * glob["renda_mediana_eur"]:
        return "de alta renda"
    if row["pct_ativos"] <= 0.5 * glob["pct_ativos"]:
        return "inativo"
    if row["pct_credito"] >= 1.5 * glob["pct_credito"] and row["pct_credito"] >= 5:
        return "tomador de crédito"
    if row["n_produtos_medio"] >= 1.3 * glob["n_produtos_medio"]:
        return "engajado"
    return "só conta"


def name_clusters(profile: pd.DataFrame, df: pd.DataFrame) -> dict[int, dict[str, str]]:
    """Gera nome curto e descrição em linguagem simples para cada cluster.

    Os nomes são um ponto de partida automático e reprodutível. Com os dados
    reais, revise-os olhando a tabela de perfil antes da apresentação.
    """
    glob = _global_profile(df)
    names: dict[int, dict[str, str]] = {}
    used: dict[str, int] = {}
    for cid, row in profile.iterrows():
        base = f"{_age_label(row['idade_media'])} {_trait(row, glob)}"
        used[base] = used.get(base, 0) + 1
        # Empate de nome: sufixo (B), (C)... — revisar manualmente via CLUSTER_NAME_OVERRIDES
        name = base if used[base] == 1 else f"{base} ({chr(ord('A') + used[base] - 1)})"
        name = config.CLUSTER_NAME_OVERRIDES.get(int(cid), name)
        description = (
            f"{fmt_num(row['tamanho_pct'], 1)}% da base · idade média {row['idade_media']:.0f} anos · "
            f"renda mediana {fmt_num(row['renda_mediana_eur'])} EUR · {row['pct_investe']:.0f}% investem · "
            f"{row['pct_ativos']:.0f}% ativos · {fmt_num(row['n_produtos_medio'], 1)} produtos em média · "
            f"predomínio de '{row['segmento_predominante']}' ({row['pct_segmento_predominante']:.0f}%)."
        )
        names[int(cid)] = {"nome": name, "descricao": description}
    return names


# ---------------------------------------------------------------------------
# Inferência (usada pelo app)
# ---------------------------------------------------------------------------
def assign_cluster(artifact: dict[str, Any], rows: pd.DataFrame) -> np.ndarray:
    """Atribui o cluster (já renumerado por tamanho) a novos clientes.

    ``rows`` precisa ter as colunas brutas: age, renta, antiguedad,
    ind_actividad_cliente, segmento e os 24 produtos (ou as contagens n_<classe>).
    """
    features = prepare_features(rows)
    raw = artifact["pipeline"].predict(features)
    return np.array([artifact["label_map"][int(c)] for c in raw])


# ---------------------------------------------------------------------------
# Figuras
# ---------------------------------------------------------------------------
def _cluster_color(cid: int) -> str:
    return config.VIZ_CATEGORICAL[cid % len(config.VIZ_CATEGORICAL)]


def fig_k_selection(metrics: pd.DataFrame, chosen: int, elbow: int) -> Figure:
    """Cotovelo (inércia), silhouette e BIC do GMM por k — um painel cada."""
    fig, axes = plt.subplots(1, 3, figsize=(15, 3.8))
    panels = [
        ("inercia", "Inércia (método do cotovelo)", "menor = clusters mais compactos"),
        ("silhouette", "Silhouette", "maior = clusters mais separados"),
        ("gmm_bic", "BIC do GMM", "menor = melhor ajuste penalizado"),
    ]
    color = config.VIZ_CATEGORICAL[0]
    for ax, (col, title, hint) in zip(axes, panels):
        ax.axvspan(config.K_MIN_BUSINESS - 0.5, config.K_MAX_BUSINESS + 0.5, color=config.VIZ_NEUTRAL_MID, zorder=0)
        ax.plot(metrics.index, metrics[col], color=color, linewidth=2, marker="o", markersize=6)
        ax.axvline(chosen, color=config.VIZ_TEXT_MUTED, linestyle="--", linewidth=1)
        ax.set(title=title, xlabel="k (número de clusters)")
        ax.text(0.99, 0.97, hint, transform=ax.transAxes, ha="right", va="top", fontsize=8, color=config.VIZ_TEXT_MUTED)
        ax.set_xticks(list(metrics.index))
        ax.grid(axis="x", visible=False)
    axes[0].annotate(f"cotovelo: k={elbow}", (elbow, metrics.loc[elbow, "inercia"]), xytext=(10, 10),
                     textcoords="offset points", fontsize=9, color=config.VIZ_TEXT_MUTED)
    axes[1].annotate(f"escolhido: k={chosen}", (chosen, metrics.loc[chosen, "silhouette"]), xytext=(10, 10),
                     textcoords="offset points", fontsize=9, color=config.VIZ_TEXT)
    fig.suptitle("Escolha de k (faixa cinza = faixa de negócio)", x=0.01, ha="left", fontweight="semibold")
    fig.tight_layout()
    return fig


def fig_cluster_sizes(profile: pd.DataFrame, names: dict[int, dict[str, str]]) -> Figure:
    """Tamanho de cada cluster, com a cor fixa do cluster."""
    fig, ax = plt.subplots(figsize=(8, 0.55 * len(profile) + 1))
    labels = [f"{cid} · {names[cid]['nome']}" for cid in profile.index]
    y = np.arange(len(profile))[::-1]
    ax.barh(y, profile["tamanho_pct"], color=[_cluster_color(c) for c in profile.index], height=0.65)
    for yi, v in zip(y, profile["tamanho_pct"]):
        ax.text(v + profile["tamanho_pct"].max() * 0.01, yi, f"{v:.1f}%", va="center", color=config.VIZ_TEXT_MUTED)
    ax.set_yticks(y, labels)
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0f}%"))
    ax.set(title="Tamanho dos clusters (% de clientes)")
    ax.grid(axis="y", visible=False)
    fig.tight_layout()
    return fig


def fig_cluster_profile(df: pd.DataFrame, labels: np.ndarray, names: dict[int, dict[str, str]]) -> Figure:
    """Heatmap: cor = desvio da média da base (em desvios-padrão); texto = valor real."""
    cols = list(PROFILE_COLUMNS)
    d = df[cols].astype(float).assign(cluster=labels)
    means = d.groupby("cluster")[cols].mean()
    z = (means - df[cols].astype(float).mean()) / df[cols].astype(float).std().replace(0, 1)
    lim = max(float(np.abs(z.values).max()), 0.5)

    neg, pos = config.VIZ_DIVERGING
    cmap = LinearSegmentedColormap.from_list("div", [neg, config.VIZ_NEUTRAL_MID, pos])
    fig, ax = plt.subplots(figsize=(1.0 * len(cols) + 3, 0.6 * len(means) + 2))
    im = ax.imshow(z.values, cmap=cmap, vmin=-lim, vmax=lim, aspect="auto")
    for i in range(z.shape[0]):
        for j, col in enumerate(cols):
            v = means.iloc[i, j]
            text = f"{np.exp(v) / 1000:.0f}k" if col == "renta_log" else (f"{v:.0%}" if v <= 1 and col in ("ind_actividad_cliente", "possui_investimento") else f"{v:.1f}")
            ax.text(j, i, text, ha="center", va="center", fontsize=8,
                    color="white" if abs(z.values[i, j]) > 0.6 * lim else config.VIZ_TEXT)
    ax.set_xticks(range(len(cols)), [PROFILE_COLUMNS[c] for c in cols], rotation=40, ha="right")
    ax.set_yticks(range(len(means)), [f"{c} · {names[c]['nome']}" for c in means.index])
    ax.grid(False)
    ax.set(title="Perfil dos clusters — vermelho: acima da média; azul: abaixo (texto = média do cluster)")
    fig.colorbar(im, ax=ax, shrink=0.8, label="desvios-padrão em relação à base")
    fig.tight_layout()
    return fig


def fig_pca_facets(X: np.ndarray, labels: np.ndarray, names: dict[int, dict[str, str]], random_state: int) -> Figure:
    """Projeção PCA 2D em small multiples: um painel por cluster, demais em cinza.

    Um único scatter com 6+ cores fica ilegível (e não é seguro para
    daltônicos); destacar um cluster por painel resolve os dois problemas.
    """
    idx = _sample_index(len(X), 5_000, random_state)
    pca = PCA(n_components=2, random_state=random_state).fit(X)
    P, lab = pca.transform(X[idx]), labels[idx]
    var = pca.explained_variance_ratio_ * 100

    k = len(names)
    ncols = min(4, k)
    nrows = int(np.ceil(k / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(3.6 * ncols, 3.3 * nrows), sharex=True, sharey=True, squeeze=False)
    for cid, ax in zip(sorted(names), axes.flat):
        ax.scatter(P[:, 0], P[:, 1], s=3, color=config.VIZ_BACKGROUND_POINTS, linewidths=0)
        sel = lab == cid
        ax.scatter(P[sel, 0], P[sel, 1], s=5, color=_cluster_color(cid), linewidths=0)
        ax.set_title(f"{cid} · {names[cid]['nome']}", fontsize=10)
        ax.grid(False)
    for ax in list(axes.flat)[k:]:
        ax.set_visible(False)
    fig.supxlabel(f"PC1 ({var[0]:.0f}% da variância)", color=config.VIZ_TEXT_MUTED, fontsize=10)
    fig.supylabel(f"PC2 ({var[1]:.0f}% da variância)", color=config.VIZ_TEXT_MUTED, fontsize=10)
    fig.suptitle("Clusters projetados em 2D (PCA) — amostra de 5 mil clientes", x=0.01, ha="left", fontweight="semibold")
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# Relatório
# ---------------------------------------------------------------------------
def _md(frame: pd.DataFrame) -> str:
    frame = frame.reset_index()
    head = "| " + " | ".join(map(str, frame.columns)) + " |"
    sep = "|" + "|".join("---" for _ in frame.columns) + "|"
    body = ["| " + " | ".join(f"{v:.3f}" if isinstance(v, float) else str(v) for v in r) + " |"
            for r in frame.itertuples(index=False)]
    return "\n".join([head, sep, *body])


@dataclass
class SegmentationResult:
    """Tudo o que a Etapa 4 produz, para relatório e testes."""

    metrics: pd.DataFrame
    elbow: int
    k: int
    comparison: pd.DataFrame
    stability: list[float]
    profile: pd.DataFrame
    names: dict[int, dict[str, str]]


def build_report(res: SegmentationResult, fig_dir: Path) -> str:
    """Relatório Markdown da segmentação."""
    rel = lambda name: (fig_dir / f"{name}.png").as_posix()  # noqa: E731
    clusters = "\n".join(
        f"- **{cid} · {v['nome']}** — {v['descricao']}" for cid, v in res.names.items()
    )
    ari = res.comparison.attrs.get("ari_entre_modelos", "n/d")
    return "\n\n".join(
        [
            "# Relatório de segmentação",
            f"Features: {', '.join(config.SEG_NUMERIC_FEATURES)} + one-hot de {', '.join(config.SEG_CATEGORICAL_FEATURES)}.",
            "## Escolha de k",
            _md(res.metrics.round(3)),
            f"Cotovelo em **k={res.elbow}**. Escolhido **k={res.k}**: maior silhouette na faixa de negócio "
            f"[{config.K_MIN_BUSINESS}, {config.K_MAX_BUSINESS}].",
            f"![Escolha de k]({rel('11_escolha_k')})",
            "## K-Means × GMM",
            _md(res.comparison),
            f"Concordância entre os dois modelos (ARI): **{ari}**.",
            "## Estabilidade (bootstrap 80%, ARI vs. modelo de referência)",
            f"{res.stability} → média **{np.mean(res.stability):.3f}**",
            "## Clusters",
            clusters,
            _md(res.profile),
            f"![Tamanhos]({rel('12_tamanho_clusters')})",
            f"![Perfil]({rel('13_perfil_clusters')})",
            f"![PCA]({rel('14_pca_clusters')})",
        ]
    ) + "\n"


# ---------------------------------------------------------------------------
# Orquestração
# ---------------------------------------------------------------------------
def run(
    input_path: Path,
    model_path: Path,
    data_path: Path,
    report_path: Path,
    fig_dir: Path,
    k_override: int | None = None,
) -> SegmentationResult:
    """Executa a Etapa 4 completa."""
    rs = config.RANDOM_STATE
    set_style()
    df = prepare_features(pd.read_parquet(input_path))
    logger.info("Base: %s clientes.", f"{len(df):,}")

    preprocessor = build_preprocessor()
    X = preprocessor.fit_transform(df)

    metrics = evaluate_k(X, config.K_RANGE, rs)
    elbow = elbow_k(metrics)
    k = k_override or choose_k(metrics, config.K_MIN_BUSINESS, config.K_MAX_BUSINESS)
    logger.info("Cotovelo k=%d | escolhido k=%d", elbow, k)

    kmeans = fit_kmeans(X, k, rs)
    gmm = fit_gmm(X, k, rs)
    label_map = relabel_by_size(kmeans.labels_)
    labels = np.array([label_map[int(c)] for c in kmeans.labels_])
    gmm_labels = gmm.predict(X)

    comparison = compare_models(X, {"K-Means": labels, "GMM": gmm_labels}, rs)
    stab = stability(X, k, rs)
    profile = profile_clusters(df, labels)
    names = name_clusters(profile, df)

    # Artefato único: pipeline treinado + metadados para o app
    artifact = {
        "pipeline": Pipeline([("prep", preprocessor), ("kmeans", kmeans)]),
        "label_map": label_map,
        "clusters": names,
        "profile": profile,
        "k": k,
        "features": {"numeric": config.SEG_NUMERIC_FEATURES, "categorical": config.SEG_CATEGORICAL_FEATURES},
        "random_state": rs,
    }
    for path in (model_path, data_path, report_path):
        path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, model_path)

    out = df.assign(
        cluster=labels.astype("int8"),
        cluster_nome=[names[c]["nome"] for c in labels],
        cluster_gmm=gmm_labels.astype("int8"),
    )
    out.to_parquet(data_path, index=False)

    save_fig(fig_k_selection(metrics, k, elbow), "11_escolha_k", fig_dir)
    save_fig(fig_cluster_sizes(profile, names), "12_tamanho_clusters", fig_dir)
    save_fig(fig_cluster_profile(df, labels, names), "13_perfil_clusters", fig_dir)
    save_fig(fig_pca_facets(X, labels, names, rs), "14_pca_clusters", fig_dir)
    plt.close("all")

    result = SegmentationResult(metrics, elbow, k, comparison, stab, profile, names)
    report_path.write_text(build_report(result, fig_dir), encoding="utf-8")
    logger.info("Salvo: %s | %s | %s", model_path, data_path, report_path)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", type=Path, default=config.PROCESSED_FILE)
    parser.add_argument("--model", type=Path, default=config.SEGMENTATION_MODEL_FILE)
    parser.add_argument("--data-out", type=Path, default=config.CLUSTERED_FILE)
    parser.add_argument("--report", type=Path, default=config.SEGMENTATION_REPORT_FILE)
    parser.add_argument("--fig-dir", type=Path, default=config.FIGURES_DIR)
    parser.add_argument("--k", type=int, default=None, help="força um k (ignora a escolha automática)")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run(args.input, args.model, args.data_out, args.report, args.fig_dir, args.k)


if __name__ == "__main__":
    main()
