"""Etapa 8 — Personas de teste com saídas esperadas.

Três personas cobrem os caminhos principais do motor de regras:

| Persona | Esperado (determinístico, independe do modelo) |
|---|---|
| Jovem, renda baixa, dívida no cartão | conservador · 5 pts · modo proteção · liquidez ≥ 60% · 0% em risco |
| Adulto moderado | moderado · 8 pts · sem proteção · ações entre 5% e 20% |
| Investidor experiente | arrojado · 13 pts · sem proteção · ações entre 20% e 45% e > liquidez |

As saídas que DEPENDEM do modelo (cluster, produtos sugeridos, pesos dentro
das faixas) são registradas no relatório, mas não são "esperadas": mudam
quando o modelo é retreinado com outros dados.

Uso:
    python -m src.personas          # usa os modelos em models/
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from src import config
from src.advisor import Artefatos, Recomendacao, aconselhar, carregar_artefatos
from src.portfolio import Carteira, Questionario
from src.utils import get_logger

logger = get_logger(__name__)

PERSONAS: dict[str, Questionario] = {
    "Jovem endividado": Questionario(
        idade=23, renda_mensal=2_000, gasto_cartao_mensal=900, reserva_emergencia=500,
        objetivo="comprar_bem", prazo="1_a_3_anos", tolerancia="venderia_parte",
        produtos=frozenset({"conta", "cartao"}), anos_conta=2,
    ),
    "Adulto moderado": Questionario(
        idade=40, renda_mensal=6_000, gasto_cartao_mensal=1_200, reserva_emergencia=40_000,
        objetivo="aposentadoria", prazo="3_a_5_anos", tolerancia="manteria",
        produtos=frozenset({"conta", "poupanca", "deposito"}), anos_conta=15,
    ),
    "Investidor experiente": Questionario(
        idade=45, renda_mensal=20_000, gasto_cartao_mensal=3_000, reserva_emergencia=200_000,
        objetivo="crescer_patrimonio", prazo="mais_de_5_anos", tolerancia="compraria_mais",
        produtos=frozenset({"conta", "deposito", "fundos", "acoes", "previdencia"}), anos_conta=20,
    ),
}


@dataclass(frozen=True)
class Expectativa:
    """Uma verificação legível ('descricao') e a função que a avalia na carteira."""

    descricao: str
    verificar: Callable[[Carteira], bool]


def _em_faixa(classe: str, lo: int, hi: int) -> Callable[[Carteira], bool]:
    return lambda c: lo <= c.alocacao[classe] <= hi


ESPERADO: dict[str, list[Expectativa]] = {
    "Jovem endividado": [
        Expectativa("perfil conservador", lambda c: c.perfil_efetivo == "conservador"),
        Expectativa("5 pontos", lambda c: c.perfil.pontos == 5),
        Expectativa("modo proteção ativo", lambda c: c.saude.modo_protecao),
        Expectativa("alertas de cartão e reserva", lambda c: c.saude.cartao_alto and c.saude.sem_reserva),
        Expectativa(f"liquidez ≥ {config.PROTECTION_LIQUIDITY_MIN}%", lambda c: c.alocacao["liquidez"] >= config.PROTECTION_LIQUIDITY_MIN),
        Expectativa("0% em ações, multimercado e previdência",
                    lambda c: c.alocacao["acoes"] == c.alocacao["multimercado"] == c.alocacao["previdencia"] == 0),
    ],
    "Adulto moderado": [
        Expectativa("perfil moderado", lambda c: c.perfil_efetivo == "moderado"),
        Expectativa("8 pontos", lambda c: c.perfil.pontos == 8),
        Expectativa("sem modo proteção", lambda c: not c.saude.modo_protecao),
        Expectativa("ações entre 5% e 20%", _em_faixa("acoes", 5, 20)),
    ],
    "Investidor experiente": [
        Expectativa("perfil arrojado", lambda c: c.perfil_efetivo == "arrojado"),
        Expectativa("13 pontos", lambda c: c.perfil.pontos == 13),
        Expectativa("sem modo proteção", lambda c: not c.saude.modo_protecao),
        Expectativa("ações entre 20% e 45%", _em_faixa("acoes", 20, 45)),
        Expectativa("ações > liquidez", lambda c: c.alocacao["acoes"] > c.alocacao["liquidez"]),
    ],
}


def avaliar(nome: str, carteira: Carteira) -> list[tuple[str, bool]]:
    """(descrição, passou?) para cada expectativa da persona."""
    return [(e.descricao, bool(e.verificar(carteira))) for e in ESPERADO[nome]]


def run(artefatos: Artefatos, report_path: Path = config.REPORTS_DIR / "personas.md") -> dict[str, Recomendacao]:
    """Roda as personas pelo fluxo completo do app e grava o relatório."""
    resultados = {nome: aconselhar(q, artefatos) for nome, q in PERSONAS.items()}
    linhas = ["# Personas de teste", "", "Esperado = regras determinísticas · Observado = saída do sistema completo.", ""]
    falhas = 0
    for nome, res in resultados.items():
        checks = avaliar(nome, res.carteira)
        falhas += sum(not ok for _, ok in checks)
        aloc = " · ".join(f"{config.BR_ASSET_CLASSES[k].split(' (')[0]} {v}%" for k, v in res.carteira.alocacao.items() if v)
        produtos = ", ".join(f"{p['rotulo']} ({p['prob']:.0%})" for p in res.produtos) or "—"
        linhas += [
            f"## {nome}",
            "",
            "| Verificação esperada | Resultado |",
            "|---|---|",
            *[f"| {d} | {'✅' if ok else '❌'} |" for d, ok in checks],
            "",
            f"- **Observado — cluster:** {res.cluster_id} · {res.cluster_nome}",
            f"- **Observado — carteira:** {aloc}",
            f"- **Observado — produtos sugeridos:** {produtos}",
            "",
        ]
    linhas.insert(3, f"**Resultado: {'todas as verificações passaram' if falhas == 0 else f'{falhas} verificação(ões) falharam'}.**\n")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(linhas), encoding="utf-8")
    logger.info("Personas: %d falha(s). Relatório: %s", falhas, report_path)
    return resultados


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--report", type=Path, default=config.REPORTS_DIR / "personas.md")
    args = parser.parse_args()
    run(carregar_artefatos(), args.report)


if __name__ == "__main__":
    main()
