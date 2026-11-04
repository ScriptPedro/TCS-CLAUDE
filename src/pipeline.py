"""Executa o projeto inteiro em um comando: Etapas 2 → 4 → 5 → Raio X → personas → auditoria.

Uso:
    python -m src.pipeline                               # caminhos padrão do config.py
    python -m src.pipeline --input outro.csv --out saida --sample-size 2000   # ensaio isolado

A referência brasileira (Raio X ANBIMA, D36) só é gerada se ``--raio-x`` existir;
sem ela, o app usa apenas o modelo.

Com ``--out``, todas as saídas vão para essa pasta (mesma estrutura do projeto),
sem tocar em data/, models/ e reports/ do projeto.
"""

from __future__ import annotations

import argparse
import time
from dataclasses import dataclass
from pathlib import Path

from src import advisor, bias_audit, config, personas, prepare_data, raio_x, recommender, segmentation
from src.utils import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class Paths:
    """Todos os arquivos produzidos pelo pipeline."""

    processed: Path
    clustered: Path
    prep_stats: Path
    seg_model: Path
    rec_model: Path
    quality_report: Path
    seg_report: Path
    rec_report: Path
    personas_report: Path
    audit_report: Path
    figures: Path
    raio_x_table: Path
    raio_x_report: Path

    @classmethod
    def default(cls) -> "Paths":
        return cls(
            config.PROCESSED_FILE, config.CLUSTERED_FILE, config.PREP_STATS_FILE,
            config.SEGMENTATION_MODEL_FILE, config.REC_MODEL_FILE,
            config.QUALITY_REPORT_FILE, config.SEGMENTATION_REPORT_FILE, config.REC_REPORT_FILE,
            config.REPORTS_DIR / "personas.md", config.REPORTS_DIR / "auditoria_vies.md",
            config.FIGURES_DIR, config.RAIO_X_FILE, config.RAIO_X_REPORT_FILE,
        )

    @classmethod
    def under(cls, root: Path) -> "Paths":
        """Mesma estrutura do projeto, mas dentro de ``root``."""
        d = cls.default()
        rel = lambda p: root / p.relative_to(config.ROOT_DIR)  # noqa: E731
        return cls(*(rel(getattr(d, f)) for f in cls.__dataclass_fields__))


def run(
    raw_csv: Path, paths: Paths, sample_size: int = config.SAMPLE_SIZE, raio_x_xlsx: Path = config.RAIO_X_RAW_FILE
) -> dict[str, object]:
    """Roda todas as etapas em sequência e devolve um resumo."""
    inicio = time.perf_counter()
    logger.info("[1/6] Preparação dos dados")
    prepare_data.run(raw_csv, paths.processed, paths.prep_stats, paths.quality_report, sample_size)

    logger.info("[2/6] Segmentação")
    seg = segmentation.run(paths.processed, paths.seg_model, paths.clustered, paths.seg_report, paths.figures)

    logger.info("[3/6] Recomendação")
    comparison, _ = recommender.run(paths.clustered, paths.rec_model, paths.rec_report, paths.figures)

    logger.info("[4/6] Referência brasileira (Raio X)")
    try:
        raio_x.run(raio_x.localizar(raio_x_xlsx), paths.raio_x_table, paths.raio_x_report)
    except FileNotFoundError as erro:
        logger.warning("Etapa do Raio X pulada (D36): %s", erro)

    logger.info("[5/6] Personas")
    artefatos = advisor.carregar_artefatos(paths.seg_model, paths.rec_model, paths.prep_stats, paths.raio_x_table)
    resultados = personas.run(artefatos, paths.personas_report)
    falhas = {
        nome: [d for d, ok in personas.avaliar(nome, r.carteira) if not ok]
        for nome, r in resultados.items()
    }

    logger.info("[6/6] Auditoria de viés")
    auditoria = bias_audit.run(paths.clustered, paths.rec_model, paths.audit_report)

    resumo = {
        "k": seg.k,
        "auc_lgbm": float(comparison.loc["LightGBM", "auc_media"]),
        "auc_cluster": float(comparison.loc["Popular no cluster", "auc_media"]),
        "referencia_br": artefatos.raio_x is not None,
        "falhas_personas": {n: f for n, f in falhas.items() if f},
        "alertas_vies": auditoria["alerts"],
        "segundos": round(time.perf_counter() - inicio, 1),
    }
    logger.info("Resumo: %s", resumo)
    return resumo


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", type=Path, default=config.RAW_FILE)
    parser.add_argument("--out", type=Path, default=None, help="pasta isolada para todas as saídas")
    parser.add_argument("--sample-size", type=int, default=config.SAMPLE_SIZE)
    parser.add_argument("--raio-x", type=Path, default=config.RAIO_X_RAW_FILE, help="microdados do Raio X (opcional)")
    args = parser.parse_args()
    paths = Paths.under(args.out) if args.out else Paths.default()
    resumo = run(args.input, paths, args.sample_size, args.raio_x)
    if resumo["falhas_personas"]:
        raise SystemExit(f"Personas com falhas: {resumo['falhas_personas']}")


if __name__ == "__main__":
    main()
