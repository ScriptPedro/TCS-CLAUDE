"""Baixa os modelos treinados de uma URL quando o contêiner sobe (deploy no Render, D42).

O plano grátis do Render não tem disco nem bucket, e os modelos não ficam no git. Então eles
vão num .zip publicado em algum lugar (ex.: anexo de uma release do GitHub), e a imagem baixa
esse .zip antes de ligar a API:

    ASSESSOR_MODELS_URL     URL do .zip com segmentation.joblib, recommender.joblib,
                            prep_stats.json e (opcional) raio_x.json — soltos ou numa subpasta
    ASSESSOR_MODELS_SHA256  opcional: SHA-256 do .zip; se não bater, nada é extraído
    ASSESSOR_MODELS_DIR     pasta de destino (a mesma que a API lê)

Sem ASSESSOR_MODELS_URL não faz nada (Docker local e Cloud Run montam a pasta, D38/D39).
Se os modelos obrigatórios já estão na pasta, também não baixa de novo.

Os .joblib são pickles: carregá-los executa código. Por isso só os nomes esperados saem do
.zip, e o SHA-256 garante que o arquivo é o mesmo que o grupo publicou.

Uso (o Dockerfile já chama antes do uvicorn):
    python -m api.modelos_remotos
"""

from __future__ import annotations

import hashlib
import io
import os
import sys
import urllib.request
import zipfile
from pathlib import Path

from src import config

OBRIGATORIOS = (
    config.SEGMENTATION_MODEL_FILE.name,
    config.REC_MODEL_FILE.name,
    config.PREP_STATS_FILE.name,
)
OPCIONAIS = (config.RAIO_X_FILE.name,)


class ErroModelos(RuntimeError):
    """O .zip não pôde ser baixado ou não tem o que a API precisa."""


def ja_tem_modelos(pasta: Path) -> bool:
    return all((pasta / nome).is_file() for nome in OBRIGATORIOS)


def baixar_bytes(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=config.MODELS_DOWNLOAD_TIMEOUT_S) as resp:  # noqa: S310 (URL do próprio grupo)
        dados = resp.read(config.MODELS_DOWNLOAD_MAX_BYTES + 1)
    if len(dados) > config.MODELS_DOWNLOAD_MAX_BYTES:
        raise ErroModelos(f"o arquivo passa de {config.MODELS_DOWNLOAD_MAX_BYTES // 2**20} MB; a URL está certa?")
    return dados


def extrair(dados: bytes, pasta: Path, sha256: str | None = None) -> list[str]:
    """Confere o hash, extrai só os arquivos de modelo conhecidos e devolve os nomes gravados."""
    if sha256:
        obtido = hashlib.sha256(dados).hexdigest()
        if obtido != sha256.strip().lower():
            raise ErroModelos(f"SHA-256 não confere (esperado {sha256.strip().lower()}, veio {obtido})")
    try:
        arquivo = zipfile.ZipFile(io.BytesIO(dados))
    except zipfile.BadZipFile as exc:
        raise ErroModelos("a URL não devolveu um .zip") from exc

    # Só o nome do arquivo conta: subpastas dentro do .zip são aceitas, "../" não escapa da pasta
    por_nome = {}
    for info in arquivo.infolist():
        nome = Path(info.filename).name
        if not info.is_dir() and nome in OBRIGATORIOS + OPCIONAIS:
            por_nome[nome] = info
    faltando = [n for n in OBRIGATORIOS if n not in por_nome]
    if faltando:
        raise ErroModelos(f"faltam no .zip: {', '.join(faltando)}")

    pasta.mkdir(parents=True, exist_ok=True)
    for nome, info in por_nome.items():
        temporario = pasta / f".{nome}.baixando"
        temporario.write_bytes(arquivo.read(info))
        temporario.replace(pasta / nome)  # troca atômica: a API nunca vê um arquivo pela metade
    return sorted(por_nome)


def preparar(url: str | None, pasta: Path, sha256: str | None = None) -> str:
    """Garante os modelos na pasta. Devolve uma frase dizendo o que aconteceu."""
    if not url:
        return "ASSESSOR_MODELS_URL não definida; usando os modelos que já estão na pasta."
    if ja_tem_modelos(pasta):
        return f"Modelos já estão em {pasta}; nada a baixar."
    gravados = extrair(baixar_bytes(url), pasta, sha256)
    return f"Modelos baixados para {pasta}: {', '.join(gravados)}."


def main() -> int:
    pasta = Path(os.environ.get("ASSESSOR_MODELS_DIR", config.MODELS_DIR))
    try:
        print(preparar(os.environ.get("ASSESSOR_MODELS_URL"), pasta, os.environ.get("ASSESSOR_MODELS_SHA256")))
    except (ErroModelos, OSError) as exc:
        # A API sobe mesmo assim: /api/saude mostra "modelos": false e o login continua funcionando
        print(f"Não foi possível preparar os modelos: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
