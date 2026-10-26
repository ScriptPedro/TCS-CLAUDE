"""Etapa 2 — Extração, amostragem e limpeza do train_ver2.csv.

Fluxo:
    1. Valida se todas as colunas esperadas existem no CSV.
    2. Lê o CSV em chunks e mantém só o snapshot ``SNAPSHOT_DATE``.
    3. Converte tipos (texto com espaços, "NA", tipos mistos).
    4. Preenche categorias/produtos ausentes e remove idades inválidas.
    5. Amostra estratificada de ``SAMPLE_SIZE`` clientes únicos por ``segmento``.
    6. Trata antiguedad e renta (winsorização p1–p99 + imputação por grupo).
    7. Salva parquet, estatísticas de limpeza (JSON) e relatório de qualidade (Markdown).

Uso:
    python -m src.prepare_data
    python -m src.prepare_data --input outro.csv --sample-size 1000   # testes
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

from src import config
from src.utils import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Estatísticas aprendidas na limpeza — o app reutiliza para tratar a entrada
# do usuário exatamente como os dados de treino foram tratados.
# ---------------------------------------------------------------------------
@dataclass
class PrepStats:
    """Parâmetros calculados durante a limpeza e o rastro de linhas removidas."""

    snapshot_date: str
    rows_read: int = 0
    rows_snapshot: int = 0
    duplicates_removed: int = 0
    invalid_age_removed: int = 0
    rows_sample: int = 0
    antiguedad_negative: int = 0
    renta_clipped: int = 0
    renta_winsor_limits: tuple[float, float] = (np.nan, np.nan)
    renta_medians: dict[str, float] = field(default_factory=dict)
    renta_global_median: float = np.nan
    antiguedad_medians: dict[str, float] = field(default_factory=dict)
    antiguedad_global_median: float = np.nan
    income_quantile_edges: list[float] = field(default_factory=list)


# ---------------------------------------------------------------------------
# 1–2. Leitura
# ---------------------------------------------------------------------------
def validate_columns(path: Path) -> None:
    """Confere se todas as colunas de ``config.USECOLS`` existem no CSV.

    Raises:
        ValueError: se alguma coluna esperada não estiver no cabeçalho.
    """
    header = set(pd.read_csv(path, nrows=0).columns.str.strip())
    missing = sorted(set(config.USECOLS) - header)
    if missing:
        raise ValueError(f"Colunas ausentes no CSV: {missing}")
    logger.info("Cabeçalho validado: %d colunas esperadas encontradas.", len(config.USECOLS))


def read_snapshot(path: Path, snapshot_date: str, chunk_size: int) -> tuple[pd.DataFrame, int]:
    """Lê o CSV em chunks e mantém apenas as linhas do snapshot.

    Colunas demográficas são lidas como texto: o arquivo tem tipos mistos
    (ex.: idade " 35", antiguedad "     -999999"), e ler como texto evita
    que o pandas adivinhe tipos diferentes em cada chunk.

    Returns:
        (DataFrame do snapshot, total de linhas lidas no arquivo)
    """
    dtypes: dict[str, str] = {c: "string" for c in [config.DATE_COL, *config.DEMOGRAPHIC_COLS]}
    dtypes.update({c: "float32" for c in config.PRODUCT_COLS})
    dtypes[config.ID_COL] = "int64"

    parts: list[pd.DataFrame] = []
    rows_read = 0
    reader = pd.read_csv(
        path,
        usecols=config.USECOLS,
        dtype=dtypes,
        chunksize=chunk_size,
        na_values=config.NA_TOKENS,
        keep_default_na=True,
    )
    for i, chunk in enumerate(reader, start=1):
        rows_read += len(chunk)
        selected = chunk[chunk[config.DATE_COL].str.strip() == snapshot_date]
        if not selected.empty:
            parts.append(selected)
        if i % 5 == 0:
            logger.info("Chunk %d: %s linhas lidas...", i, f"{rows_read:,}")

    if not parts:
        raise ValueError(f"Nenhuma linha com {config.DATE_COL} == {snapshot_date}")

    df = pd.concat(parts, ignore_index=True)
    logger.info("Snapshot %s: %s linhas de %s lidas.", snapshot_date, f"{len(df):,}", f"{rows_read:,}")
    return df, rows_read


# ---------------------------------------------------------------------------
# 3–4. Tipos, categorias e filtros
# ---------------------------------------------------------------------------
def coerce_types(df: pd.DataFrame) -> pd.DataFrame:
    """Remove espaços, transforma tokens de ausência em NaN e converte números.

    Não imputa nada: a saída serve para medir os nulos "reais" (antes).
    """
    df = df.copy()
    text_cols = [config.DATE_COL, *config.CATEGORICAL_COLS, *config.NUMERIC_TEXT_COLS]
    for col in text_cols:
        df[col] = df[col].str.strip().replace(config.NA_TOKENS, pd.NA)

    for col in config.NUMERIC_TEXT_COLS:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")

    df[config.DATE_COL] = pd.to_datetime(df[config.DATE_COL])
    return df


def fill_categoricals_and_products(df: pd.DataFrame) -> pd.DataFrame:
    """Padroniza categorias e preenche ausências que têm semântica clara.

    - Categorias ausentes viram ``UNKNOWN_LABEL`` (não descartamos o cliente).
    - Produto ausente = não possui (0). Ocorre em ind_nomina/ind_nom_pens.
    - Flags de atividade/novo cliente ausentes = 0 (sem evidência).
    """
    df = df.copy()
    df["segmento"] = df["segmento"].map(config.SEGMENT_MAP)
    for col in config.CATEGORICAL_COLS:
        df[col] = df[col].fillna(config.UNKNOWN_LABEL).astype("string")

    df[config.PRODUCT_COLS] = df[config.PRODUCT_COLS].fillna(0).astype("int8")
    for col in ["ind_actividad_cliente", "ind_nuevo"]:
        df[col] = df[col].fillna(0).astype("int8")
    return df


def drop_duplicate_clients(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Garante 1 linha por cliente no snapshot (salvaguarda; esperado = 0)."""
    before = len(df)
    df = df.drop_duplicates(subset=config.ID_COL, keep="last")
    removed = before - len(df)
    if removed:
        logger.warning("%d linhas duplicadas de ncodpers removidas.", removed)
    return df, removed


def filter_valid_age(df: pd.DataFrame, age_min: int, age_max: int) -> tuple[pd.DataFrame, int]:
    """Remove idades ausentes ou fora de [age_min, age_max]."""
    mask = df["age"].between(age_min, age_max)
    removed = int((~mask).sum())
    logger.info("Idade fora de [%d, %d] ou nula: %s clientes removidos.", age_min, age_max, f"{removed:,}")
    return df.loc[mask].copy(), removed


# ---------------------------------------------------------------------------
# 5. Amostragem
# ---------------------------------------------------------------------------
def stratified_sample(df: pd.DataFrame, n: int, strat_col: str, random_state: int) -> pd.DataFrame:
    """Amostra ``n`` clientes preservando a proporção de ``strat_col``.

    Se a base tiver ``n`` linhas ou menos, retorna tudo.
    """
    if len(df) <= n:
        logger.warning("Base tem %d linhas (<= %d); usando todas.", len(df), n)
        return df.reset_index(drop=True)

    sample, _ = train_test_split(
        df, train_size=n, stratify=df[strat_col], random_state=random_state
    )
    logger.info("Amostra estratificada por '%s': %s clientes.", strat_col, f"{len(sample):,}")
    return sample.reset_index(drop=True)


# ---------------------------------------------------------------------------
# 6. Tratamento de idade, antiguedad e renta
# ---------------------------------------------------------------------------
def add_age_band(df: pd.DataFrame) -> pd.DataFrame:
    """Cria ``faixa_etaria`` (categórica ordenada) a partir de ``age``."""
    df = df.copy()
    df["age"] = df["age"].astype("int16")
    df["faixa_etaria"] = pd.cut(
        df["age"], bins=config.AGE_BINS, labels=config.AGE_LABELS, right=False
    )
    return df


def _group_key(*values: object) -> str:
    """Chave textual para salvar medianas por grupo em JSON."""
    return "|".join(str(v) for v in values)


def clean_antiguedad(df: pd.DataFrame, stats: PrepStats) -> pd.DataFrame:
    """Trata antiguedad (meses de relacionamento).

    Valores negativos (ex.: -999999, código de "desconhecido") viram NaN e
    são imputados pela mediana da faixa etária. A coluna
    ``antiguedad_imputada`` registra quais linhas foram imputadas.
    """
    df = df.copy()
    negative = df["antiguedad"] < 0
    stats.antiguedad_negative = int(negative.sum())
    df.loc[negative, "antiguedad"] = np.nan
    df["antiguedad_imputada"] = df["antiguedad"].isna().astype("int8")

    medians = df.groupby("faixa_etaria", observed=True)["antiguedad"].median()
    stats.antiguedad_medians = {_group_key(k): float(v) for k, v in medians.dropna().items()}
    stats.antiguedad_global_median = float(df["antiguedad"].median())

    fill = df.groupby("faixa_etaria", observed=True)["antiguedad"].transform("median")
    df["antiguedad"] = (
        df["antiguedad"].fillna(fill).fillna(stats.antiguedad_global_median).astype("int16")
    )
    logger.info("antiguedad: %d valores imputados.", int(df["antiguedad_imputada"].sum()))
    return df


def winsorize_renta(df: pd.DataFrame, stats: PrepStats) -> pd.DataFrame:
    """Limita renta aos percentis p1–p99 dos valores observados."""
    df = df.copy()
    low, high = df["renta"].quantile([config.WINSOR_LOWER_Q, config.WINSOR_UPPER_Q])
    stats.renta_winsor_limits = (float(low), float(high))
    stats.renta_clipped = int(((df["renta"] < low) | (df["renta"] > high)).sum())
    df["renta"] = df["renta"].clip(lower=low, upper=high)
    logger.info(
        "renta winsorizada em [%.0f, %.0f]: %d valores ajustados.", low, high, stats.renta_clipped
    )
    return df


def impute_renta(df: pd.DataFrame, stats: PrepStats) -> pd.DataFrame:
    """Imputa renta nula pela mediana de (segmento × faixa etária).

    Fallback: mediana global, para grupos sem nenhuma renda observada.
    """
    df = df.copy()
    df["renta_imputada"] = df["renta"].isna().astype("int8")

    group_cols = ["segmento", "faixa_etaria"]
    medians = df.groupby(group_cols, observed=True)["renta"].median()
    stats.renta_medians = {_group_key(*k): float(v) for k, v in medians.dropna().items()}
    stats.renta_global_median = float(df["renta"].median())

    fill = df.groupby(group_cols, observed=True)["renta"].transform("median")
    df["renta"] = df["renta"].fillna(fill).fillna(stats.renta_global_median)
    logger.info("renta: %d valores imputados.", int(df["renta_imputada"].sum()))
    return df


def add_income_quantile(df: pd.DataFrame, stats: PrepStats) -> pd.DataFrame:
    """Cria ``renta_quintil`` (faixa relativa de renda) — ver decisão D3."""
    df = df.copy()
    df["renta_quintil"], edges = pd.qcut(
        df["renta"],
        q=config.N_INCOME_QUANTILES,
        labels=config.INCOME_QUANTILE_LABELS,
        retbins=True,
    )
    stats.income_quantile_edges = [float(e) for e in edges]
    return df


# ---------------------------------------------------------------------------
# 7. Saídas
# ---------------------------------------------------------------------------
def null_table(df: pd.DataFrame) -> pd.Series:
    """Percentual de nulos por coluna."""
    return (df.isna().mean() * 100).round(2)


def _md_table(frame: pd.DataFrame) -> str:
    """Converte um DataFrame pequeno em tabela Markdown (sem dependências extras)."""
    header = "| " + " | ".join(str(c) for c in frame.columns) + " |"
    sep = "|" + "|".join("---" for _ in frame.columns) + "|"
    rows = ["| " + " | ".join(str(v) for v in row) + " |" for row in frame.itertuples(index=False)]
    return "\n".join([header, sep, *rows])


def build_quality_report(
    nulls_before: pd.Series,
    nulls_after: pd.Series,
    segment_population: pd.Series,
    final: pd.DataFrame,
    stats: PrepStats,
) -> str:
    """Monta o relatório de qualidade em Markdown."""
    nulls = pd.DataFrame({"% nulos antes": nulls_before, "% nulos depois": nulls_after})
    nulls = (
        nulls[nulls.fillna(0).ne(0).any(axis=1)]  # só colunas que tiveram algum nulo
        .fillna("—")
        .reset_index(names="coluna")
    )

    segment = pd.DataFrame(
        {
            "% população (snapshot)": (segment_population * 100).round(2),
            "% amostra": (final["segmento"].value_counts(normalize=True) * 100).round(2),
        }
    ).reset_index(names="segmento")

    describe = (
        final[["age", "renta", "antiguedad"]].describe().T.round(1).reset_index(names="variável")
    )

    ownership = (
        (final[config.PRODUCT_COLS].mean() * 100)
        .round(2)
        .sort_values(ascending=False)
        .rename("% clientes com o produto")
        .rename_axis("produto")
        .reset_index()
    )

    funnel = pd.DataFrame(
        {
            "etapa": [
                "Linhas lidas no CSV",
                f"Linhas no snapshot {stats.snapshot_date}",
                "Duplicatas de ncodpers removidas",
                "Removidos por idade inválida",
                "Amostra final (clientes únicos)",
            ],
            "quantidade": [
                f"{stats.rows_read:,}",
                f"{stats.rows_snapshot:,}",
                f"{stats.duplicates_removed:,}",
                f"{stats.invalid_age_removed:,}",
                f"{stats.rows_sample:,}",
            ],
        }
    )

    low, high = stats.renta_winsor_limits
    return "\n\n".join(
        [
            "# Relatório de qualidade dos dados",
            f"Gerado por `src/prepare_data.py` · `random_state={config.RANDOM_STATE}`",
            "## Funil de linhas",
            _md_table(funnel),
            f"Shape final: **{final.shape[0]:,} linhas × {final.shape[1]} colunas**",
            "## Nulos antes × depois",
            "Antes = snapshot após conversão de tipos; depois = amostra final. "
            "Colunas sem nulos foram omitidas.",
            _md_table(nulls),
            "## Valores inválidos tratados (na amostra)",
            f"- antiguedad negativa (código de desconhecido) → imputada: **{stats.antiguedad_negative:,}**\n"
            f"- renta fora de p1–p99 → winsorizada: **{stats.renta_clipped:,}**",
            "## Estratificação por segmento",
            _md_table(segment),
            "## Distribuições numéricas (amostra final)",
            f"renta winsorizada em [{low:,.0f}; {high:,.0f}] EUR (p1–p99).",
            _md_table(describe),
            "## Posse de produtos (amostra final)",
            _md_table(ownership),
        ]
    ) + "\n"


def save_outputs(
    df: pd.DataFrame, stats: PrepStats, report: str, output: Path, stats_path: Path, report_path: Path
) -> None:
    """Grava parquet, JSON de estatísticas e relatório Markdown."""
    for path in (output, stats_path, report_path):
        path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(output, index=False)
    stats_path.write_text(json.dumps(asdict(stats), indent=2, ensure_ascii=False), encoding="utf-8")
    report_path.write_text(report, encoding="utf-8")
    logger.info("Salvo: %s | %s | %s", output, stats_path, report_path)


# ---------------------------------------------------------------------------
# Orquestração
# ---------------------------------------------------------------------------
FINAL_COLUMNS: list[str] = [
    config.ID_COL, config.DATE_COL,
    "age", "faixa_etaria",
    "renta", "renta_imputada", "renta_quintil",
    "antiguedad", "antiguedad_imputada",
    "sexo", "segmento", "ind_actividad_cliente", "ind_nuevo", "canal_entrada",
    *config.PRODUCT_COLS,
]


def run(input_path: Path, output: Path, stats_path: Path, report_path: Path, sample_size: int) -> pd.DataFrame:
    """Executa o pipeline completo da Etapa 2 e devolve a amostra limpa."""
    stats = PrepStats(snapshot_date=config.SNAPSHOT_DATE)

    validate_columns(input_path)
    raw, stats.rows_read = read_snapshot(input_path, config.SNAPSHOT_DATE, config.CHUNK_SIZE)
    stats.rows_snapshot = len(raw)

    typed = coerce_types(raw)
    nulls_before = null_table(typed)

    df = fill_categoricals_and_products(typed)
    df, stats.duplicates_removed = drop_duplicate_clients(df)
    df, stats.invalid_age_removed = filter_valid_age(df, config.AGE_MIN, config.AGE_MAX)
    segment_population = df[config.STRATIFY_COL].value_counts(normalize=True)

    df = stratified_sample(df, sample_size, config.STRATIFY_COL, config.RANDOM_STATE)
    stats.rows_sample = len(df)

    df = add_age_band(df)
    df = clean_antiguedad(df, stats)
    df = winsorize_renta(df, stats)
    df = impute_renta(df, stats)
    df = add_income_quantile(df, stats)
    df = df[FINAL_COLUMNS]

    report = build_quality_report(nulls_before, null_table(df), segment_population, df, stats)
    save_outputs(df, stats, report, output, stats_path, report_path)
    return df


def parse_args() -> argparse.Namespace:
    """Argumentos de linha de comando (padrões vêm do config.py)."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", type=Path, default=config.RAW_FILE)
    parser.add_argument("--output", type=Path, default=config.PROCESSED_FILE)
    parser.add_argument("--stats", type=Path, default=config.PREP_STATS_FILE)
    parser.add_argument("--report", type=Path, default=config.QUALITY_REPORT_FILE)
    parser.add_argument("--sample-size", type=int, default=config.SAMPLE_SIZE)
    return parser.parse_args()


def main() -> None:
    """Ponto de entrada do script."""
    args = parse_args()
    if not args.input.exists():
        logger.error("Arquivo não encontrado: %s. Rode antes: python -m src.download_data", args.input)
        raise SystemExit(1)
    run(args.input, args.output, args.stats, args.report, args.sample_size)


if __name__ == "__main__":
    main()
