"""Coerência dos arquivos de deploy (D38): imagem enxuta, mas com as mesmas versões do projeto."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _pins(arquivo: Path) -> dict[str, str]:
    pins = {}
    for linha in arquivo.read_text(encoding="utf-8").splitlines():
        linha = linha.split("#", 1)[0].strip()
        if linha:
            nome, versao = linha.split("==")
            pins[nome.strip().lower()] = versao.strip()
    return pins


def test_requirements_deploy_usa_as_mesmas_versoes():
    """Os .joblib só carregam com as mesmas versões de scikit-learn/LightGBM usadas no treino."""
    projeto = _pins(ROOT / "requirements.txt")
    deploy = _pins(ROOT / "requirements-deploy.txt")
    assert deploy, "requirements-deploy.txt vazio"
    for nome, versao in deploy.items():
        assert nome in projeto, f"{nome} está no deploy mas não no requirements.txt"
        assert projeto[nome] == versao, f"{nome}: deploy {versao} ≠ projeto {projeto[nome]}"


def test_requirements_deploy_tem_o_que_a_api_precisa():
    deploy = _pins(ROOT / "requirements-deploy.txt")
    for nome in ("fastapi", "uvicorn", "scikit-learn", "lightgbm", "shap", "joblib", "pandas"):
        assert nome in deploy, f"falta {nome} no requirements-deploy.txt"


def test_dockerfile_aponta_para_a_pasta_montada_pelo_terraform():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    main_tf = (ROOT / "infra" / "terraform" / "main.tf").read_text(encoding="utf-8")
    assert "ASSESSOR_MODELS_DIR=/models" in dockerfile
    assert re.search(r'mount_path\s*=\s*"/models"', main_tf)
    assert "requirements-deploy.txt" in dockerfile
