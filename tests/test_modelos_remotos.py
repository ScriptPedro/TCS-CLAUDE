"""Download dos modelos no Render (D42): só os arquivos esperados, com hash conferido."""

from __future__ import annotations

import hashlib
import io
import zipfile
from pathlib import Path

import pytest

from api import modelos_remotos as mr


def _zip(arquivos: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for nome, dados in arquivos.items():
            z.writestr(nome, dados)
    return buf.getvalue()


COMPLETO = {nome: f"conteudo de {nome}".encode() for nome in mr.OBRIGATORIOS}


def test_extrai_os_modelos_mesmo_dentro_de_subpasta(tmp_path: Path) -> None:
    dados = _zip({f"models/{n}": d for n, d in COMPLETO.items()} | {"models/raio_x.json": b"{}"})
    gravados = mr.extrair(dados, tmp_path / "m")
    assert gravados == sorted([*mr.OBRIGATORIOS, "raio_x.json"])
    assert (tmp_path / "m" / "prep_stats.json").read_bytes() == COMPLETO["prep_stats.json"]
    assert mr.ja_tem_modelos(tmp_path / "m")


def test_ignora_arquivos_estranhos_e_caminhos_para_fora(tmp_path: Path) -> None:
    dados = _zip(COMPLETO | {"../../fora.joblib": b"x", "script.py": b"x", "../segmentation.joblib": b"y"})
    pasta = tmp_path / "a" / "m"
    mr.extrair(dados, pasta)
    assert sorted(p.name for p in pasta.iterdir()) == sorted(mr.OBRIGATORIOS)
    assert not (tmp_path / "fora.joblib").exists()
    assert not (tmp_path / "a" / "segmentation.joblib").exists()


def test_recusa_zip_incompleto_ou_que_nao_e_zip(tmp_path: Path) -> None:
    with pytest.raises(mr.ErroModelos, match="recommender.joblib"):
        mr.extrair(_zip({"segmentation.joblib": b"x", "prep_stats.json": b"{}"}), tmp_path)
    with pytest.raises(mr.ErroModelos, match="zip"):
        mr.extrair(b"<html>Not Found</html>", tmp_path)
    assert not any(tmp_path.iterdir())


def test_confere_o_sha256(tmp_path: Path) -> None:
    dados = _zip(COMPLETO)
    with pytest.raises(mr.ErroModelos, match="SHA-256"):
        mr.extrair(dados, tmp_path, sha256="0" * 64)
    assert not any(tmp_path.iterdir())
    mr.extrair(dados, tmp_path, sha256=hashlib.sha256(dados).hexdigest().upper() + "\n")
    assert mr.ja_tem_modelos(tmp_path)


def test_preparar_baixa_uma_vez_e_sem_url_nao_faz_nada(tmp_path: Path) -> None:
    origem = tmp_path / "modelos.zip"
    origem.write_bytes(_zip(COMPLETO))
    pasta = tmp_path / "m"
    assert "não definida" in mr.preparar(None, pasta)
    assert not pasta.exists()
    assert "baixados" in mr.preparar(origem.as_uri(), pasta)
    assert "nada a baixar" in mr.preparar(origem.as_uri(), pasta)


def test_main_falha_sem_derrubar_e_avisa(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                         capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setenv("ASSESSOR_MODELS_DIR", str(tmp_path / "m"))
    monkeypatch.setenv("ASSESSOR_MODELS_URL", (tmp_path / "nao_existe.zip").as_uri())
    assert mr.main() == 1
    assert "Não foi possível preparar os modelos" in capsys.readouterr().err
