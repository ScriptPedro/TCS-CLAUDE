"""Referência brasileira — Raio X do Investidor Brasileiro (ANBIMA/Datafolha), decisão D36.

O modelo de recomendação continua treinado no Santander (clientes espanhóis).
Este módulo NÃO treina modelo: ele calcula, a partir dos microdados da pesquisa,
a fração de brasileiros que usa cada classe da carteira, por faixa de renda
individual × faixa de idade (com peso amostral). O app usa essa tabela para:

    1. ajustar a afinidade, ou seja, onde cada classe fica DENTRO da faixa do
       perfil (``portfolio.afinidade_por_classe``). As faixas não mudam (D25);
    2. explicar ao usuário "o que brasileiros parecidos fazem" × "o que o seu
       perfil pede".

Só as colunas de idade, renda, peso e produtos são lidas. Cor, religião,
orientação sexual e gênero nunca são carregados (LGPD, D11).

Uso:
    python -m src.raio_x            # lê config.RAIO_X_RAW_FILE e gera models/raio_x.json + reports/raio_x.md
"""

from __future__ import annotations

import argparse
import json
from bisect import bisect_right
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src import config
from src.utils import fmt_num, get_logger

logger = get_logger(__name__)

CLASSES: list[str] = list(config.BR_ASSET_CLASSES)


# ---------------------------------------------------------------------------
# Leitura
# ---------------------------------------------------------------------------
def _colunas_usadas(nome: Any) -> bool:
    nome = str(nome)
    fixas = {config.RAIO_X_ID_COL, config.RAIO_X_AGE_COL, config.RAIO_X_INCOME_COL, config.RAIO_X_WEIGHT_COL}
    prefixo = config.RAIO_X_PRODUCT_PREFIX
    return nome in fixas or (nome.startswith(prefixo) and len(nome) == len(prefixo) + 1 and nome[-1].isalpha())


def localizar(xlsx: Path) -> Path:
    """Caminho do arquivo; se não existir, procura um .xlsx com "raio" e "x" no nome na mesma pasta.

    Evita falhar só porque o arquivo foi salvo com outro nome (ex.: ``raio_x_2026.xlsx``).
    """
    xlsx = Path(xlsx)
    if xlsx.exists():
        return xlsx
    pasta = xlsx.parent
    candidatos = sorted(
        p for p in (pasta.glob("*.xlsx") if pasta.is_dir() else [])
        if "raio" in p.name.lower() and "x" in p.name.lower().replace("xlsx", "")
    )
    if len(candidatos) == 1:
        logger.info("Usando %s (não achei %s)", candidatos[0], xlsx.name)
        return candidatos[0]
    zips = sorted(p.name for p in pasta.glob("*.zip")) if pasta.is_dir() else []
    dica = f" Há .zip na pasta ({', '.join(zips)}): extraia o .xlsx antes." if zips else ""
    varios = f" Achei vários candidatos: {', '.join(p.name for p in candidatos)}; use --input." if candidatos else ""
    raise FileNotFoundError(
        f"Microdados do Raio X não encontrados em {xlsx}.{varios}{dica} Baixe os 'dados brutos' em "
        "https://www.anbima.com.br/pt_br/especial/raio-x-do-investidor-brasileiro.htm, extraia o .xlsx e "
        f"salve em {pasta} (ou rode: python -m src.raio_x --input <caminho do .xlsx>)."
    )


def ler(xlsx: Path) -> pd.DataFrame:
    """Lê apenas as colunas necessárias da aba codificada (uma linha por entrevistado)."""
    df = pd.read_excel(xlsx, sheet_name=config.RAIO_X_SHEET, usecols=_colunas_usadas)
    faltando = {config.RAIO_X_AGE_COL, config.RAIO_X_INCOME_COL, config.RAIO_X_WEIGHT_COL} - set(df.columns)
    if faltando:
        raise ValueError(f"Colunas ausentes no Raio X: {sorted(faltando)}")
    logger.info("Raio X: %d entrevistados, %d colunas lidas", len(df), df.shape[1])
    return df


def preparar(df: pd.DataFrame) -> pd.DataFrame:
    """Uma linha por entrevistado: faixa de renda, faixa de idade, peso e posse por classe (0/1)."""
    produtos = [c for c in df.columns if c.startswith(config.RAIO_X_PRODUCT_PREFIX)]
    codigos = df[produtos].apply(pd.to_numeric, errors="coerce")
    out = pd.DataFrame({
        "faixa_renda": pd.to_numeric(df[config.RAIO_X_INCOME_COL], errors="coerce").map(config.RAIO_X_INCOME_CODE_TO_BAND),
        "faixa_idade": np.searchsorted(config.RAIO_X_AGE_EDGES, pd.to_numeric(df[config.RAIO_X_AGE_COL]), side="right"),
        "peso": pd.to_numeric(df[config.RAIO_X_WEIGHT_COL], errors="coerce").fillna(1.0),
    })
    for classe in CLASSES:
        cods = [c for c, k in config.RAIO_X_PRODUCT_TO_BR_CLASS.items() if k == classe]
        out[classe] = codigos.isin(cods).any(axis=1).astype(int)
    out["algum_investimento"] = out[CLASSES].max(axis=1)
    return out


# ---------------------------------------------------------------------------
# Tabela de referência
# ---------------------------------------------------------------------------
COLUNAS_TAXA: list[str] = [*CLASSES, "algum_investimento"]


def _taxas(grupo: pd.DataFrame) -> pd.Series:
    w = grupo["peso"]
    return grupo[COLUNAS_TAXA].mul(w, axis=0).sum() / w.sum()


def construir_tabela(dados: pd.DataFrame, shrink: float = config.RAIO_X_SHRINK) -> dict[str, Any]:
    """Taxas ponderadas por faixa de renda × idade, suavizadas em direção à média da renda.

    taxa_célula = (Σ peso·posse + shrink·taxa_renda) / (Σ peso + shrink)

    Quem não declarou renda (sem renda, recusa, não sabe) entra só na média geral.
    """
    validos = dados.dropna(subset=["faixa_renda"]).astype({"faixa_renda": int})
    n_renda, n_idade = len(config.RAIO_X_INCOME_LABELS), len(config.RAIO_X_AGE_LABELS)
    geral = _taxas(dados)
    celulas: list[list[dict[str, Any]]] = []
    por_renda: list[dict[str, Any]] = []
    for r in range(n_renda):
        grupo_r = validos[validos["faixa_renda"] == r]
        base = _taxas(grupo_r) if len(grupo_r) else geral
        por_renda.append({"n": int(len(grupo_r)), **base.round(4).to_dict()})
        linha = []
        for i in range(n_idade):
            g = grupo_r[grupo_r["faixa_idade"] == i]
            soma_w = float(g["peso"].sum())
            soma = g[COLUNAS_TAXA].mul(g["peso"], axis=0).sum() if len(g) else 0.0 * base
            taxa = (soma + shrink * base) / (soma_w + shrink)
            linha.append({"n": int(len(g)), **taxa.round(4).to_dict()})
        celulas.append(linha)
    por_idade = [{"n": int((dados["faixa_idade"] == i).sum()), **_taxas(dados[dados["faixa_idade"] == i]).round(4).to_dict()}
                 for i in range(n_idade)]
    return {
        "fonte": config.RAIO_X_SOURCE,
        "n_entrevistados": int(len(dados)),
        "classes": CLASSES,
        "renda_limites": config.RAIO_X_INCOME_EDGES,
        "renda_rotulos": config.RAIO_X_INCOME_LABELS,
        "idade_limites": config.RAIO_X_AGE_EDGES,
        "idade_rotulos": config.RAIO_X_AGE_LABELS,
        "suavizacao": shrink,
        "geral": {"n": int(len(dados)), **geral.round(4).to_dict()},
        "por_renda": por_renda,
        "por_idade": por_idade,
        "celulas": celulas,   # celulas[faixa_renda][faixa_idade]
    }


# ---------------------------------------------------------------------------
# Consulta (usada pelo advisor)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ReferenciaBR:
    """O que brasileiros da mesma faixa de renda e idade usam (frações 0–1)."""

    faixa_renda: str
    faixa_idade: str
    n: int
    posse: dict[str, float]          # classe da carteira → fração que usa
    algum_investimento: float        # fração com ao menos um produto financeiro da carteira
    fonte: str

    @property
    def amostra_pequena(self) -> bool:
        return self.n < config.RAIO_X_MIN_CELL


def referencia(tabela: dict[str, Any], idade: int, renda_mensal: float) -> ReferenciaBR:
    """Célula da tabela correspondente à idade e à renda mensal (R$) do usuário."""
    r = bisect_right(tabela["renda_limites"], renda_mensal - 1e-9)   # limite superior pertence à faixa
    i = bisect_right(tabela["idade_limites"], idade)
    cel = tabela["celulas"][r][i]
    return ReferenciaBR(
        faixa_renda=tabela["renda_rotulos"][r],
        faixa_idade=tabela["idade_rotulos"][i],
        n=int(cel["n"]),
        posse={c: float(cel[c]) for c in tabela["classes"]},
        algum_investimento=float(cel["algum_investimento"]),
        fonte=tabela["fonte"],
    )


def carregar(path: Path = config.RAIO_X_FILE) -> dict[str, Any] | None:
    """Tabela salva, ou None se a etapa ainda não foi executada (o app funciona sem ela)."""
    path = Path(path)
    if not path.exists():
        logger.info("Referência brasileira ausente (%s): afinidade só com o modelo.", path)
        return None
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Relatório
# ---------------------------------------------------------------------------
NOMES: dict[str, str] = {
    "liquidez": "Poupança (liquidez)", "renda_fixa": "Renda fixa (CDB, Tesouro...)", "multimercado": "Fundos",
    "acoes": "Ações", "previdencia": "Previdência", "algum_investimento": "Algum desses",
}


def _pct(x: float) -> str:
    return fmt_num(100 * x, 1) + "%"


def _tabela_md(linhas: list[dict[str, Any]], rotulos: list[str], titulo: str) -> list[str]:
    cab = [titulo, "n", *(NOMES[c] for c in COLUNAS_TAXA)]
    out = ["| " + " | ".join(cab) + " |", "|" + "---|" * len(cab)]
    for rot, lin in zip(rotulos, linhas):
        out.append("| " + " | ".join([rot, str(lin["n"]), *(_pct(lin[c]) for c in COLUNAS_TAXA)]) + " |")
    return out


def escrever_relatorio(tabela: dict[str, Any], path: Path) -> None:
    g = tabela["geral"]
    linhas = [
        "# Referência brasileira — Raio X do Investidor",
        "",
        f"Fonte: {tabela['fonte']}. Microdados com {fmt_num(tabela['n_entrevistados'])} entrevistados, "
        "taxas ponderadas pelo peso amostral (`PESOE`). Pergunta usada: P9, *investimentos que utiliza atualmente*.",
        "",
        "**Uso no projeto (D36):** complementa o modelo treinado no Santander. Ajusta onde cada classe fica "
        "**dentro** da faixa do perfil e alimenta a explicação. Não define o perfil nem as faixas.",
        "",
        f"No geral, **{_pct(g['algum_investimento'])}** usam ao menos um dos produtos financeiros da carteira "
        f"(poupança, renda fixa, fundos, ações ou previdência).",
        "",
        "## Por faixa de renda individual (mensal)",
        "",
        *_tabela_md(tabela["por_renda"], tabela["renda_rotulos"], "Renda"),
        "",
        "## Por faixa de idade",
        "",
        *_tabela_md(tabela["por_idade"], tabela["idade_rotulos"], "Idade"),
        "",
        "## Entrevistados por célula (renda × idade)",
        "",
        "| Renda | " + " | ".join(tabela["idade_rotulos"]) + " |",
        "|---|" + "---|" * len(tabela["idade_rotulos"]),
        *("| " + rot + " | " + " | ".join(str(c["n"]) for c in linha) + " |"
          for rot, linha in zip(tabela["renda_rotulos"], tabela["celulas"])),
        "",
        f"Células com menos de {config.RAIO_X_MIN_CELL} entrevistados são aproximadas: a taxa é suavizada em direção "
        f"à média da faixa de renda (equivalente a {fmt_num(tabela['suavizacao'])} entrevistados).",
        "",
        "## Mapeamento P9 → classe da carteira",
        "",
        "| Resposta da pesquisa | Classe |",
        "|---|---|",
        "| Caderneta de poupança | liquidez |",
        "| Títulos públicos (Tesouro Direto) e títulos privados (CDB, LCI, LCA...) | renda_fixa |",
        "| Fundos de investimento (todos os tipos) | multimercado (analogia) |",
        "| Ações na bolsa | acoes |",
        "| Previdência privada | previdencia |",
        "",
        "## Limitações",
        "",
        "- Posse **declarada** pelo entrevistado, não registrada pelo banco.",
        "- Mostra o que as pessoas **fazem**, não o que é adequado: por isso nunca define o perfil nem as faixas.",
        "- \"Fundos\" mistura renda fixa, multimercado, ações e imobiliário.",
        "- A pesquisa não classifica o entrevistado como conservador, moderado ou arrojado.",
        "- Cor, religião, orientação sexual e gênero não são lidos (LGPD).",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    logger.info("Relatório salvo em %s", path)


def run(
    xlsx: Path = config.RAIO_X_RAW_FILE,
    out_json: Path = config.RAIO_X_FILE,
    report: Path = config.RAIO_X_REPORT_FILE,
) -> dict[str, Any]:
    """Lê os microdados, gera a tabela de referência e o relatório."""
    tabela = construir_tabela(preparar(ler(localizar(Path(xlsx)))))
    out_json = Path(out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(tabela, ensure_ascii=False, indent=1), encoding="utf-8")
    logger.info("Tabela de referência salva em %s", out_json)
    escrever_relatorio(tabela, Path(report))
    return tabela


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", type=Path, default=config.RAIO_X_RAW_FILE)
    parser.add_argument("--out", type=Path, default=config.RAIO_X_FILE)
    parser.add_argument("--report", type=Path, default=config.RAIO_X_REPORT_FILE)
    args = parser.parse_args()
    run(args.input, args.out, args.report)


if __name__ == "__main__":
    main()
