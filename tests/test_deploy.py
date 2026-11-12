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
    gcp = (ROOT / "infra" / "gcp" / "main.tf").read_text(encoding="utf-8")
    docker = (ROOT / "infra" / "docker" / "main.tf").read_text(encoding="utf-8")
    assert "ASSESSOR_MODELS_DIR=/models" in dockerfile
    assert re.search(r'mount_path\s*=\s*"/models"', gcp)
    assert re.search(r'container_path\s*=\s*"/models"', docker)
    assert "requirements-deploy.txt" in dockerfile


def test_postgres_dos_usuarios_no_docker():
    """D41: a API aponta para o contêiner do Postgres, e os dados dele ficam num volume."""
    docker = (ROOT / "infra" / "docker" / "main.tf").read_text(encoding="utf-8")
    assert 'resource "docker_container" "postgres"' in docker
    assert "ASSESSOR_DATABASE_URL=postgresql://assessor:${var.senha_postgres}@${docker_container.postgres.name}:5432/assessor" in docker
    assert re.search(r'volume_name\s*=\s*local\.volume_postgres\s*\n\s*container_path\s*=\s*"/var/lib/postgresql/data"', docker)
    assert "ports" not in docker.split('resource "docker_container" "postgres"')[1].split("resource ")[0]  # sem porta aberta


def test_imagem_tem_o_driver_do_postgres():
    deploy = _pins(ROOT / "requirements-deploy.txt")
    assert "psycopg[binary]" in deploy


# ---------------------------------------------------------------------------
# Render + GitHub Pages (D42)
# ---------------------------------------------------------------------------
def test_dockerfile_baixa_os_modelos_antes_de_ligar_a_api():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    cmd = next(linha for linha in dockerfile.splitlines() if linha.startswith("CMD"))
    # ";" e não "&&": sem os modelos, a API sobe assim mesmo e /api/saude mostra o problema
    assert "python -m api.modelos_remotos; exec uvicorn" in cmd
    assert "chown assessor /models" in dockerfile


def test_blueprint_do_render():
    render = (ROOT / "render.yaml").read_text(encoding="utf-8")
    assert "dockerfilePath: ./Dockerfile" in render
    assert "healthCheckPath: /api/saude" in render
    for chave in ("ASSESSOR_DATABASE_URL", "ASSESSOR_MODELS_URL", "ASSESSOR_CORS_ORIGINS"):
        assert f"key: {chave}" in render
    assert re.search(r"fromDatabase:\s*\n\s*name: assessor-db\s*\n\s*property: connectionString", render)
    assert re.search(r"databases:\s*\n\s*- name: assessor-db", render)
    # O banco e a API na mesma região, senão o endereço interno do banco não funciona
    assert len(set(re.findall(r"region: (\w+)", render))) == 1


def test_workflow_do_pages_passa_a_api_e_a_subpasta():
    workflow = (ROOT / ".github" / "workflows" / "pages.yml").read_text(encoding="utf-8")
    assert "VITE_API_URL: ${{ vars.API_URL }}" in workflow
    assert "VITE_BASE: /${{ github.event.repository.name }}/" in workflow
    assert "path: frontend/dist" in workflow
    vite = (ROOT / "frontend" / "vite.config.ts").read_text(encoding="utf-8")
    assert "VITE_BASE" in vite
    assert "VITE_API_URL" in (ROOT / "frontend" / "src" / "api.ts").read_text(encoding="utf-8")


def test_cors_libera_o_pages_que_o_workflow_publica():
    render = (ROOT / "render.yaml").read_text(encoding="utf-8")
    origem = re.search(r"key: ASSESSOR_CORS_ORIGINS[^\n]*\n\s*value: (\S+)", render).group(1)
    assert origem == "https://scriptpedro.github.io"  # origem = só esquema + host, sem a subpasta
