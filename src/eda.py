"""Etapa 3 — Funções de análise exploratória (gráficos, tabelas e insights).

O notebook ``notebooks/01_eda.ipynb`` só chama estas funções: a lógica fica
versionada e testável aqui, e o notebook fica limpo para a apresentação.
Todas as figuras são salvas em PNG (``docs/figures``) para ir direto aos slides.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.figure import Figure
from matplotlib.patches import Patch

from src import config
from src.features import add_group_counts
from src.utils import get_logger

logger = get_logger(__name__)

# Classes que fazem sentido em gráficos de "penetração" (crédito fica de fora: não recomendamos)
RECOMMENDABLE_GROUPS: list[str] = [
    g for g in config.PRODUCT_GROUPS if g not in config.NON_RECOMMENDABLE_GROUPS
]
BY_LABELS: dict[str, str] = {
    "faixa_etaria": "Faixa etária",
    "renta_quintil": "Quintil de renda",
    "segmento": "Segmento",
}
PRODUCT_GROUP_OF: dict[str, str] = {
    p: g for g, cols in config.PRODUCT_GROUPS.items() for p in cols
}


# ---------------------------------------------------------------------------
# Preparação
# ---------------------------------------------------------------------------
def load_processed(path: Path = config.PROCESSED_FILE) -> pd.DataFrame:
    """Lê o parquet da Etapa 2 e adiciona as contagens por classe de produto."""
    df = pd.read_parquet(path)
    logger.info("Base carregada: %s linhas × %d colunas.", f"{len(df):,}", df.shape[1])
    return add_group_counts(df)


def set_style() -> None:
    """Estilo visual único para todas as figuras (eixos e grade discretos)."""
    plt.rcParams.update(
        {
            "figure.facecolor": config.VIZ_SURFACE,
            "axes.facecolor": config.VIZ_SURFACE,
            "savefig.facecolor": config.VIZ_SURFACE,
            "axes.edgecolor": config.VIZ_GRID,
            "axes.labelcolor": config.VIZ_TEXT_MUTED,
            "axes.titlecolor": config.VIZ_TEXT,
            "axes.titlesize": 12,
            "axes.titleweight": "semibold",
            "axes.titlelocation": "left",
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "axes.axisbelow": True,  # grade atrás das barras
            "grid.color": config.VIZ_GRID,
            "grid.linewidth": 0.8,
            "xtick.color": config.VIZ_TEXT_MUTED,
            "ytick.color": config.VIZ_TEXT_MUTED,
            "text.color": config.VIZ_TEXT,
            "legend.frameon": False,
            "font.size": 10,
        }
    )


def save_fig(fig: Figure, name: str, out_dir: Path = config.FIGURES_DIR) -> Path:
    """Salva a figura em PNG e devolve o caminho."""
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{name}.png"
    fig.savefig(path, dpi=config.VIZ_DPI, bbox_inches="tight")
    logger.info("Figura salva: %s", path)
    return path


def _sequential_cmap() -> LinearSegmentedColormap:
    return LinearSegmentedColormap.from_list("seq_azul", config.VIZ_SEQUENTIAL)


def _diverging_cmap() -> LinearSegmentedColormap:
    neg, pos = config.VIZ_DIVERGING
    return LinearSegmentedColormap.from_list("div", [neg, config.VIZ_NEUTRAL_MID, pos])


def _pct_axis(ax: plt.Axes, axis: str = "y") -> None:
    fmt = plt.FuncFormatter(lambda v, _: f"{v:.0f}%")
    (ax.yaxis if axis == "y" else ax.xaxis).set_major_formatter(fmt)


# ---------------------------------------------------------------------------
# Tabelas
# ---------------------------------------------------------------------------
def ownership_rate(df: pd.DataFrame) -> pd.DataFrame:
    """% de clientes que possuem cada produto, com classe e rótulo legível."""
    rate = (df[config.PRODUCT_COLS].mean() * 100).rename("pct")
    out = rate.to_frame()
    out["produto"] = out.index.map(config.PRODUCT_LABELS)
    out["classe"] = out.index.map(PRODUCT_GROUP_OF)
    return out.sort_values("pct", ascending=False)


def group_penetration_by(df: pd.DataFrame, by: str) -> pd.DataFrame:
    """% de clientes com ao menos 1 produto de cada classe, por categoria de ``by``."""
    flags = pd.DataFrame(
        {g: (df[f"n_{g}"] > 0) for g in config.PRODUCT_GROUPS} | {"investimento": df["possui_investimento"] > 0}
    )
    flags[by] = df[by]
    return flags.groupby(by, observed=True).mean().mul(100).round(2)


def product_rate_by(df: pd.DataFrame, by: str, min_pct: float = 0.5) -> pd.DataFrame:
    """% de posse por produto × categoria de ``by`` (produtos raros omitidos)."""
    keep = ownership_rate(df).query("pct >= @min_pct").index
    table = df.groupby(by, observed=True)[list(keep)].mean().mul(100).T
    table.index = table.index.map(config.PRODUCT_LABELS)
    return table.round(1)


def product_correlation(df: pd.DataFrame) -> pd.DataFrame:
    """Correlação phi entre produtos (Pearson em variáveis 0/1).

    Produtos constantes (ninguém ou todos possuem) são removidos: a
    correlação deles é indefinida.
    """
    cols = [c for c in config.PRODUCT_COLS if df[c].nunique() > 1]
    corr = df[cols].astype(float).corr()
    labels = [config.PRODUCT_LABELS[c] for c in cols]
    corr.index, corr.columns = labels, labels
    return corr


def top_correlated_pairs(df: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    """Os ``n`` pares de produtos com maior |correlação|."""
    corr = product_correlation(df)
    mask = np.triu(np.ones(corr.shape, dtype=bool), k=1)
    pairs = corr.where(mask).stack().rename("phi").reset_index()
    pairs.columns = ["produto_a", "produto_b", "phi"]
    return (
        pairs.reindex(pairs["phi"].abs().sort_values(ascending=False).index)
        .head(n)
        .round(3)
        .reset_index(drop=True)
    )


# ---------------------------------------------------------------------------
# Figuras
# ---------------------------------------------------------------------------
def fig_distributions(df: pd.DataFrame) -> Figure:
    """Histogramas de idade, renda (escala log) e tempo de relacionamento."""
    fig, axes = plt.subplots(1, 3, figsize=(14, 3.8))
    color = config.VIZ_GROUP_COLORS["liquidez"]

    axes[0].hist(df["age"], bins=range(18, 102, 2), color=color, edgecolor=config.VIZ_SURFACE, linewidth=0.6)
    axes[0].set(title="Idade", xlabel="anos", ylabel="clientes")

    bins = np.logspace(np.log10(df["renta"].min()), np.log10(df["renta"].max()), 40)
    axes[1].hist(df["renta"], bins=bins, color=color, edgecolor=config.VIZ_SURFACE, linewidth=0.6)
    axes[1].set_xscale("log")
    axes[1].xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v / 1000:.0f} mil"))
    axes[1].set(title="Renda anual bruta (escala log, após winsorização)", xlabel="EUR")

    axes[2].hist(df["antiguedad"] / 12, bins=30, color=color, edgecolor=config.VIZ_SURFACE, linewidth=0.6)
    axes[2].set(title="Tempo de relacionamento", xlabel="anos")

    for ax in axes:
        ax.grid(axis="x", visible=False)
    fig.tight_layout()
    return fig


def fig_segments(df: pd.DataFrame) -> Figure:
    """Tamanho de cada segmento e distribuição de idade dentro dele."""
    order = df["segmento"].value_counts().index.tolist()
    fig, axes = plt.subplots(1, 2, figsize=(12, 3.8), gridspec_kw={"width_ratios": [1, 1.4]})
    color = config.VIZ_GROUP_COLORS["liquidez"]

    pct = df["segmento"].value_counts(normalize=True).reindex(order) * 100
    axes[0].barh(order[::-1], pct[::-1], color=color, height=0.6)
    for y, v in enumerate(pct[::-1]):
        axes[0].text(v + pct.max() * 0.01, y, f"{v:.1f}%", va="center", color=config.VIZ_TEXT_MUTED)
    axes[0].set(title="Clientes por segmento")
    axes[0].grid(axis="y", visible=False)
    _pct_axis(axes[0], "x")

    data = [df.loc[df["segmento"] == s, "age"] for s in order]
    bp = axes[1].boxplot(data, vert=False, tick_labels=order, patch_artist=True, widths=0.5, showfliers=False)
    for box in bp["boxes"]:
        box.set(facecolor=config.VIZ_SEQUENTIAL[1], edgecolor=color)
    for key in ("whiskers", "caps", "medians"):
        for line in bp[key]:
            line.set(color=color, linewidth=1.5)
    axes[1].invert_yaxis()
    axes[1].set(title="Idade por segmento", xlabel="anos")
    axes[1].grid(axis="y", visible=False)
    fig.tight_layout()
    return fig


def fig_product_ownership(df: pd.DataFrame, n_labels: int = 8) -> Figure:
    """Ranking de posse dos 24 produtos, colorido pela classe."""
    rate = ownership_rate(df).iloc[::-1]
    colors = rate["classe"].map(config.VIZ_GROUP_COLORS)
    fig, ax = plt.subplots(figsize=(9, 8))
    ax.barh(rate["produto"], rate["pct"], color=colors, height=0.72)

    # Rótulos só nos produtos mais comuns (leitura seletiva, sem poluir)
    offset = rate["pct"].max() * 0.01
    for y, (pct, rank) in enumerate(zip(rate["pct"], range(len(rate), 0, -1))):
        if rank <= n_labels:
            ax.text(pct + offset, y, f"{pct:.1f}%", va="center", color=config.VIZ_TEXT_MUTED, fontsize=9)

    handles = [Patch(color=config.VIZ_GROUP_COLORS[g], label=config.GROUP_LABELS[g]) for g in config.PRODUCT_GROUPS]
    ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(1.02, 1), title="Classe")
    ax.set(title="% de clientes que possuem cada produto")
    ax.grid(axis="y", visible=False)
    _pct_axis(ax, "x")
    fig.tight_layout()
    return fig


def fig_products_per_client(df: pd.DataFrame) -> Figure:
    """Distribuição do número de produtos por cliente."""
    counts = df["n_produtos"].value_counts(normalize=True).sort_index() * 100
    fig, ax = plt.subplots(figsize=(7, 3.5))
    ax.bar(counts.index.astype(str), counts.values, color=config.VIZ_GROUP_COLORS["liquidez"], width=0.7)
    ax.set(title="Quantos produtos cada cliente possui", xlabel="nº de produtos", ylabel="% de clientes")
    ax.grid(axis="x", visible=False)
    _pct_axis(ax)
    fig.tight_layout()
    return fig


def fig_penetration_by(df: pd.DataFrame, by: str) -> Figure:
    """Small multiples: % com ao menos 1 produto de cada classe, por ``by``.

    Um painel por classe (cada um com sua escala): liquidez fica perto de
    100% e renda variável em poucos %, então um eixo único esconderia a
    variação das classes pequenas.
    """
    table = group_penetration_by(df, by)
    fig, axes = plt.subplots(1, len(RECOMMENDABLE_GROUPS), figsize=(15, 3.6), sharex=True)
    x = table.index.astype(str)
    for ax, group in zip(axes, RECOMMENDABLE_GROUPS):
        ax.bar(x, table[group], color=config.VIZ_GROUP_COLORS[group], width=0.7)
        ax.set_title(config.GROUP_LABELS[group], fontsize=11)
        ax.set_ylim(0, max(table[group].max() * 1.15, 1))
        ax.grid(axis="x", visible=False)
        ax.tick_params(axis="x", rotation=45)
        _pct_axis(ax)
    axes[0].set_ylabel("% de clientes com ≥ 1 produto")
    fig.suptitle(f"Posse por classe de produto × {BY_LABELS.get(by, by).lower()}", x=0.01, ha="left", fontweight="semibold")
    fig.tight_layout()
    return fig


def fig_heatmap_by(df: pd.DataFrame, by: str, min_pct: float = 0.5) -> Figure:
    """Heatmap de % de posse por produto × categoria de ``by``."""
    table = product_rate_by(df, by, min_pct)
    fig, ax = plt.subplots(figsize=(1.2 * table.shape[1] + 3, 0.42 * table.shape[0] + 1.5))
    im = ax.imshow(table.values, cmap=_sequential_cmap(), aspect="auto", vmin=0)
    vmax = np.nanmax(table.values)
    for i in range(table.shape[0]):
        for j in range(table.shape[1]):
            v = table.values[i, j]
            ax.text(j, i, f"{v:.1f}", ha="center", va="center", fontsize=8,
                    color="white" if v > 0.55 * vmax else config.VIZ_TEXT)
    ax.set_xticks(range(table.shape[1]), table.columns.astype(str))
    ax.set_yticks(range(table.shape[0]), table.index)
    ax.grid(False)
    ax.set(title=f"% de posse por produto × {BY_LABELS.get(by, by).lower()}")
    fig.colorbar(im, ax=ax, shrink=0.8, format="%.0f%%")
    fig.tight_layout()
    return fig


def fig_correlation(df: pd.DataFrame, annotate_min: float = 0.2) -> Figure:
    """Matriz de correlação (phi) entre produtos, só o triângulo inferior."""
    corr = product_correlation(df)
    # Triângulo inferior sem a diagonal: a 1ª linha e a última coluna ficariam vazias
    masked = corr.where(np.tril(np.ones(corr.shape, dtype=bool), k=-1)).iloc[1:, :-1]
    lim = max(float(np.nanmax(np.abs(masked.values))), 0.1)

    fig, ax = plt.subplots(figsize=(11, 9))
    im = ax.imshow(masked.values, cmap=_diverging_cmap(), vmin=-lim, vmax=lim)
    for i in range(masked.shape[0]):
        for j in range(i + 1):
            v = masked.values[i, j]
            if abs(v) >= annotate_min:
                ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=7,
                        color="white" if abs(v) > 0.6 * lim else config.VIZ_TEXT)
    ax.set_xticks(range(masked.shape[1]), masked.columns, rotation=90)
    ax.set_yticks(range(masked.shape[0]), masked.index)
    ax.grid(False)
    ax.spines[["left", "bottom"]].set_visible(False)
    ax.set(title=f"Correlação entre produtos (phi) — valores anotados quando |phi| ≥ {annotate_min}")
    fig.colorbar(im, ax=ax, shrink=0.7)
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# Insights calculados (os números vêm dos dados, não são escritos à mão)
# ---------------------------------------------------------------------------
def generate_insights(df: pd.DataFrame) -> list[str]:
    """Gera frases com números reais da base, prontas para os slides."""
    insights: list[str] = []
    rate = ownership_rate(df)
    top3 = ", ".join(f"{r.produto} ({r.pct:.1f}%)" for r in rate.head(3).itertuples())
    insights.append(f"Base: {len(df):,} clientes; média de {df['n_produtos'].mean():.2f} produtos por cliente; "
                    f"{(df['n_produtos'] == 0).mean():.1%} não têm nenhum produto ativo.")
    insights.append(f"Produtos mais comuns: {top3}.")

    only_liq = ((df["n_liquidez"] > 0) & (df["possui_investimento"] == 0)).mean()
    insights.append(f"{df['possui_investimento'].mean():.1%} dos clientes têm algum investimento; "
                    f"{only_liq:.1%} têm só produtos de conta/liquidez — o público-alvo do assessor.")

    by_income = group_penetration_by(df, "renta_quintil")["investimento"]
    low, high = by_income.iloc[0], by_income.iloc[-1]
    ratio = f"{high / low:.1f}×" if low > 0 else "n/d"
    insights.append(f"Posse de investimento por renda: {low:.1f}% no quintil mais baixo vs "
                    f"{high:.1f}% no mais alto ({ratio}).")

    by_age = group_penetration_by(df, "faixa_etaria")["investimento"]
    insights.append(f"Faixa etária que mais investe: {by_age.idxmax()} ({by_age.max():.1f}%); "
                    f"a que menos investe: {by_age.idxmin()} ({by_age.min():.1f}%).")

    by_seg = group_penetration_by(df, "segmento")["investimento"].sort_values(ascending=False)
    insights.append("Posse de investimento por segmento: "
                    + ", ".join(f"{s} {v:.1f}%" for s, v in by_seg.items()) + ".")

    pair = top_correlated_pairs(df, 1).iloc[0]
    insights.append(f"Par de produtos mais associado: {pair.produto_a} × {pair.produto_b} (phi = {pair.phi:.2f}) "
                    "— candidatos a recomendação conjunta.")

    card = df.groupby("possui_investimento")["ind_tjcr_fin_ult1"].mean() * 100
    if len(card) == 2:
        insights.append(f"Cartão de crédito: {card.get(1, 0):.1f}% entre investidores vs "
                        f"{card.get(0, 0):.1f}% entre não investidores.")

    insights.append(f"Renda imputada em {df['renta_imputada'].mean():.1%} dos clientes "
                    "— limitação a citar na banca.")
    return insights
