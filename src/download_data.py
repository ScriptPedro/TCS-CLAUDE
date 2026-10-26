"""Baixa o train_ver2.csv da competição Santander Product Recommendation (Kaggle).

Pré-requisitos:
    1. Conta no Kaggle e regras da competição ACEITAS na página da competição.
    2. Token da API em ~/.kaggle/kaggle.json (Windows: C:\\Users\\<voce>\\.kaggle\\kaggle.json).

Uso:
    python -m src.download_data
"""

from __future__ import annotations

import shutil
import subprocess
import zipfile
from pathlib import Path

from src import config
from src.utils import get_logger

logger = get_logger(__name__)


def kaggle_credentials_exist() -> bool:
    """Verifica se o token da API do Kaggle está no local padrão."""
    return (Path.home() / ".kaggle" / "kaggle.json").exists()


def download_zip(dest_dir: Path) -> Path:
    """Executa ``kaggle competitions download`` para o arquivo de treino.

    Args:
        dest_dir: pasta de destino (data/raw).

    Returns:
        Caminho do .zip baixado.
    """
    if shutil.which("kaggle") is None:
        raise RuntimeError("CLI do Kaggle não encontrada. Rode: pip install -r requirements.txt")

    cmd = [
        "kaggle", "competitions", "download",
        "-c", config.KAGGLE_COMPETITION,
        "-f", config.KAGGLE_FILE,
        "-p", str(dest_dir),
    ]
    logger.info("Executando: %s", " ".join(cmd))
    subprocess.run(cmd, check=True)
    return dest_dir / config.KAGGLE_FILE


def extract_zip(zip_path: Path, dest_dir: Path) -> None:
    """Descompacta o .zip em ``dest_dir`` e remove o arquivo compactado."""
    logger.info("Descompactando %s (~2,3 GB descompactado)...", zip_path.name)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(dest_dir)
    zip_path.unlink()


def main() -> None:
    """Orquestra o download, pulando etapas já concluídas."""
    config.RAW_DIR.mkdir(parents=True, exist_ok=True)

    if config.RAW_FILE.exists():
        logger.info("Arquivo já existe em %s — nada a fazer.", config.RAW_FILE)
        return

    if not kaggle_credentials_exist():
        logger.error(
            "Token não encontrado em ~/.kaggle/kaggle.json. "
            "Gere em kaggle.com > Settings > API > Create New Token."
        )
        raise SystemExit(1)

    zip_path = download_zip(config.RAW_DIR)
    extract_zip(zip_path, config.RAW_DIR)
    logger.info("Pronto: %s", config.RAW_FILE)


if __name__ == "__main__":
    main()
