"""API HTTP do Assessor de Investimentos Virtual (back-end do front React).

Expõe o mesmo fluxo do app Streamlit, sem duplicar lógica: as perguntas vêm de
``app.components`` e a decisão de ``src.advisor`` / ``src.portfolio``.

    GET  /api/saude          → os modelos estão carregados?
    GET  /api/questionario   → etapas, perguntas, opções e respostas padrão
    POST /api/recomendacao   → respostas do formulário → recomendação completa

Uso (na raiz do projeto):
    uvicorn api.main:app --reload --port 8000

Se ``frontend/dist`` existir (``npm run build``), o front também é servido aqui,
em http://localhost:8000. ASSESSOR_MODELS_DIR aponta para outra pasta de modelos.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app import components as ui
from src import config
from src.advisor import Artefatos, Recomendacao, aconselhar, carregar_artefatos
from src.portfolio import (
    DIMENSOES, RESPOSTAS_LEGIVEIS, explicar_classe, por_mil, proximos_passos, resumo_simples, risco_carteira,
)

ROOT = Path(__file__).resolve().parents[1]
FRONT_DIST = ROOT / "frontend" / "dist"

app = FastAPI(title="Assessor de Investimentos Virtual", version="1.0.0")


def pasta_modelos() -> Path:
    return Path(os.environ.get("ASSESSOR_MODELS_DIR", config.MODELS_DIR))


@lru_cache(maxsize=4)
def _artefatos(models_dir: str) -> Artefatos:
    pasta = Path(models_dir)
    return carregar_artefatos(
        pasta / config.SEGMENTATION_MODEL_FILE.name,
        pasta / config.REC_MODEL_FILE.name,
        pasta / config.PREP_STATS_FILE.name,
    )


def obter_artefatos() -> Artefatos:
    """Carrega os modelos uma vez por pasta (a pasta pode mudar entre testes)."""
    return _artefatos(str(pasta_modelos()))


# ---------------------------------------------------------------------------
# Questionário
# ---------------------------------------------------------------------------
def _pergunta(campo: str) -> dict[str, Any]:
    p = ui.PERGUNTAS[campo]
    return {
        "campo": campo,
        "texto": p.texto,
        "tipo": p.tipo,
        "opcoes": [{"valor": o, "rotulo": p.rotulo(o)} for o in p.opcoes],
        "padrao": p.padrao,
        "ajuda": p.ajuda,
        "horizontal": p.horizontal,
    }


@app.get("/api/questionario")
def questionario() -> dict[str, Any]:
    return {
        "etapas": [
            {"titulo": titulo, "descricao": descricao, "perguntas": [_pergunta(c) for c in campos]}
            for titulo, descricao, campos in ui.ETAPAS
        ],
        "padrao": ui.respostas_padrao(),
        "aviso": config.DISCLAIMER,
    }


@app.get("/api/saude")
def saude() -> dict[str, Any]:
    try:
        obter_artefatos()
    except FileNotFoundError as exc:
        return {"modelos": False, "erro": str(exc)}
    return {"modelos": True, "erro": None}


# ---------------------------------------------------------------------------
# Recomendação
# ---------------------------------------------------------------------------
class Respostas(BaseModel):
    respostas: dict[str, Any]


def _classe(res: Recomendacao, classe: str) -> dict[str, Any]:
    c = res.carteira
    info = config.CLASS_INFO[classe]
    lo, hi = c.faixas[classe]
    return {
        "classe": classe,
        "nome": info["nome"],
        "pct": c.alocacao[classe],
        "por_mil": por_mil(c.alocacao[classe]),
        "cor": ui.CLASS_COLORS[classe],
        "o_que_e": info["o_que_e"],
        "papel": info["papel"],
        "risco": config.RISK_LEVEL_LABELS[info["risco"]],
        "resgate": info["resgate"],
        "motivo": explicar_classe(c, classe),
        "minimo": lo,
        "maximo": hi,
        "afinidade": c.afinidade[classe],
    }


def serializar(res: Recomendacao, avisos: list[str]) -> dict[str, Any]:
    """Tudo o que a tela de resultado mostra, em JSON. Textos podem conter **negrito**."""
    c = res.carteira
    nota, rotulo_risco = risco_carteira(c)
    classes = sorted(config.BR_ASSET_CLASSES, key=lambda k: -c.alocacao[k])
    return {
        "avisos": avisos,
        "resumo": resumo_simples(c),
        "perfil": {
            "efetivo": c.perfil_efetivo,
            "pela_soma": c.perfil.perfil_pela_soma,
            "pontos": c.perfil.pontos,
            "pontos_max": c.perfil.pontos_max,
            "limitado_por": c.perfil.limitado_por,
            "detalhamento": [
                {"pergunta": DIMENSOES[d], "resposta": RESPOSTAS_LEGIVEIS.get(r, r), "pontos": pts}
                for d, (r, pts) in c.perfil.detalhamento.items()
            ],
        },
        "risco": {"nota": round(nota, 2), "rotulo": rotulo_risco},
        "segmento": {"id": res.cluster_id, "nome": res.cluster_nome, "descricao": res.cluster_descricao},
        "saude": {"modo_protecao": c.saude.modo_protecao, "alertas": c.saude.alertas},
        "carteira": [_classe(res, k) for k in classes],
        "proximos_passos": proximos_passos(c),
        "produtos": [
            {
                "rotulo": p["rotulo"],
                "classe_br": p["classe_br"],
                "prob": float(p["prob"]),
                "fatores": [{"texto": t, "direcao": "alta" if d == "↑" else "baixa"}
                            for t, d in ui.fatores_legiveis(p["fatores"])],
            }
            for p in res.produtos
        ],
        "texto": res.texto,
        "aviso": res.aviso,
    }


@app.post("/api/recomendacao")
def recomendacao(body: Respostas) -> dict[str, Any]:
    q, erros = ui.montar_questionario(body.respostas)
    if erros:
        raise HTTPException(status_code=422, detail={"erros": erros})
    try:
        artefatos = obter_artefatos()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail={"erros": [f"Modelos não encontrados. {exc}"]}) from exc
    return serializar(aconselhar(q, artefatos), ui.avisos_de_consistencia(q))


# ---------------------------------------------------------------------------
# Front compilado (opcional)
# ---------------------------------------------------------------------------
if FRONT_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONT_DIST / "assets"), name="assets")

    @app.get("/{caminho:path}", include_in_schema=False)
    def front(caminho: str) -> FileResponse:
        arquivo = (FRONT_DIST / caminho).resolve()
        dentro = arquivo.is_relative_to(FRONT_DIST.resolve())  # bloqueia "../" fora da pasta
        return FileResponse(arquivo if caminho and dentro and arquivo.is_file() else FRONT_DIST / "index.html")
