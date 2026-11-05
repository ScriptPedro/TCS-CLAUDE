"""Assessor conversacional (D37): o usuário pergunta sobre a própria carteira.

O modelo de linguagem só EXPLICA e SIMULA. Todo número vem do código já testado:
    - o contexto (perfil, faixas, carteira, produtos, referência brasileira) sai de
      ``src.advisor.aconselhar``;
    - a ferramenta ``simular_cenario`` muda respostas do questionário e roda o
      assessor de novo ("e se eu quitar o cartão?").

Privacidade (LGPD, D37): o modelo recebe faixas e rótulos (ex.: renda "R$ 4.000 a
R$ 7.000", "35 a 44 anos"), nunca a idade exata nem valores digitados.

Usado pela API (``POST /api/conversa``) e pelo app Streamlit. Testável sem rede:
os testes passam um provedor falso no lugar do Gemini.
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass, field
from typing import Any

from app import components as ui
from src import config, llm
from src.advisor import Artefatos, Recomendacao, aconselhar
from src.llm import AssistenteIndisponivel, ChamadaFerramenta, Ferramenta, Mensagem, Provedor
from src.portfolio import (
    DIMENSOES, RESPOSTAS_LEGIVEIS, comparacao_brasil, explicar_classe, passos_calculo, proximos_passos, risco_carteira,
)

__all__ = ["AssistenteIndisponivel", "RespostaConversa", "conversar", "ferramentas", "contexto", "obter_provedor"]

obter_provedor = llm.obter_provedor  # ponto único de troca (os testes substituem por um provedor falso)

INSTRUCOES = """Você é o assistente do "Assessor de Investimentos Virtual", um projeto acadêmico.
O usuário acabou de receber uma carteira sugerida e quer entendê-la. Regras:

1. Responda em português do Brasil, em linguagem simples, em até 150 palavras.
2. Use SOMENTE os dados do CONTEXTO abaixo e os resultados da ferramenta. Nunca invente
   porcentagens, valores, taxas, rentabilidades ou prazos. Se o dado não estiver aqui, diga
   que o assessor não calcula isso.
3. Perguntas do tipo "e se..." (quitar dívida, completar a reserva, mudar prazo, objetivo,
   reação a quedas etc.): chame a ferramenta simular_cenario e compare antes × depois com os
   números que ela devolver.
4. Não indique ativos, fundos, ações, bancos ou corretoras específicos. Fale só das classes
   da carteira (liquidez, renda fixa, multimercado, ações/ETFs, previdência).
5. O perfil (conservador, moderado, arrojado) e as faixas vêm de regras de suitability; o
   modelo de IA e o costume dos brasileiros só posicionam cada classe dentro da faixa.
   Nunca sugira sair das faixas do perfil. Se o modo proteção estiver ativo, reforce que a
   prioridade é organizar a base antes de investir com risco.
6. Não peça nem repita dados pessoais (nome, CPF, contato, valores exatos).
7. Fora do tema (carteira, finanças pessoais, o próprio assessor): recuse com educação.
8. Se pedirem uma decisão ("devo investir?"), lembre que é uma simulação acadêmica e não
   uma recomendação de investimento, e indique um profissional certificado.
"""


@dataclass
class RespostaConversa:
    texto: str
    simulacoes: list[dict[str, Any]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Contexto enviado ao modelo (só faixas e números calculados pelo assessor)
# ---------------------------------------------------------------------------
def faixa_etaria(idade: int) -> str:
    return config.RAIO_X_AGE_LABELS[bisect_right(config.RAIO_X_AGE_EDGES, idade)]


def respostas_legiveis(respostas: dict[str, Any]) -> dict[str, str]:
    """Pergunta → resposta em texto, com a idade trocada pela faixa etária."""
    out = {}
    for campo, p in ui.PERGUNTAS.items():
        valor = respostas.get(campo)
        if campo == "idade":
            out["Faixa etária"] = faixa_etaria(int(valor))
        elif isinstance(valor, list):
            out[p.texto] = ", ".join(p.rotulo(v) for v in valor) or "nenhum"
        elif valor is not None:
            out[p.texto] = p.rotulo(valor)
    return out


def contexto(res: Recomendacao, respostas: dict[str, Any]) -> str:
    c = res.carteira
    p = c.perfil
    _, rotulo_risco = risco_carteira(c)
    linhas = ["## Respostas do usuário (em faixas)"]
    linhas += [f"- {k}: {v}" for k, v in respostas_legiveis(respostas).items()]
    linhas += [
        "\n## Perfil de risco",
        f"- Perfil usado: {c.perfil_efetivo} (pela soma dos pontos seria {p.perfil_pela_soma}; {p.pontos} de {p.pontos_max} pontos)",
        *[f"- {DIMENSOES[d]}: {RESPOSTAS_LEGIVEIS.get(r, r)} → {pts} pt" for d, (r, pts) in p.detalhamento.items()],
        *[f"- Limite aplicado: {lim}" for lim in p.limitado_por],
        "\n## Saúde financeira",
        f"- Modo proteção: {'ATIVO' if c.saude.modo_protecao else 'não'}",
        *[f"- Alerta: {a}" for a in c.saude.alertas],
        "\n## Carteira sugerida (de cada R$ 1.000)",
    ]
    for classe, pct in sorted(c.alocacao.items(), key=lambda kv: -kv[1]):
        info = config.CLASS_INFO[classe]
        lo, hi = c.faixas[classe]
        linhas.append(
            f"- {info['nome']}: {pct}% (faixa do perfil {lo:.0f}% a {hi:.0f}%). O que é: {info['o_que_e']} "
            f"Risco: {config.RISK_LEVEL_LABELS[info['risco']]}. Resgate: {info['resgate']}. Por quê: {explicar_classe(c, classe)}"
        )
    linhas += [f"- Risco estimado da carteira: {rotulo_risco}", "\n## Como a carteira foi calculada"]
    linhas += [f"{i}. {passo}" for i, passo in enumerate(passos_calculo(c), 1)]
    linhas += ["\n## Próximos passos sugeridos", *[f"- {passo}" for passo in proximos_passos(c)]]
    linhas += [f"\n## Grupo de clientes parecidos (segmentação)\n- {res.cluster_nome}: {res.cluster_descricao}"]
    if res.produtos:
        linhas.append("\n## Produtos para conhecer (modelo de IA treinado com clientes de banco)")
        for prod in res.produtos:
            fatores = ", ".join(f"{t} ({d})" for t, d in ui.fatores_legiveis(prod["fatores"]))
            linhas.append(f"- {prod['rotulo']}: {prod['prob']:.0%} dos clientes parecidos têm. Fatores: {fatores or '—'}")
    if c.referencia_br is not None:
        linhas += ["\n## Brasileiros parecidos (Raio X do Investidor, ANBIMA)", *[f"- {frase}" for frase in comparacao_brasil(c)]]
    linhas.append(f"\n## Aviso\n{config.DISCLAIMER}")
    return "\n".join(linhas)


# ---------------------------------------------------------------------------
# Ferramenta: simular_cenario
# ---------------------------------------------------------------------------
CAMPOS_SIMULAVEIS: list[str] = [c for c in ui.PERGUNTAS if c != "idade"]  # idade exata não sai do servidor


def _esquema_campo(campo: str) -> dict[str, Any]:
    p = ui.PERGUNTAS[campo]
    opcoes = "; ".join(f"{o} = {p.rotulo(o)}" for o in p.opcoes)
    descricao = f"{p.texto} Opções: {opcoes}."
    if p.tipo == "multipla":
        return {"type": "array", "items": {"type": "string", "enum": p.opcoes}, "description": descricao}
    return {"type": "string", "enum": p.opcoes, "description": descricao}


def ferramentas() -> list[Ferramenta]:
    return [Ferramenta(
        nome="simular_cenario",
        descricao=(
            "Recalcula a recomendação como se o usuário tivesse respondido diferente algumas perguntas "
            "(ex.: quitou a dívida cara, completou a reserva, aceita esperar mais). Informe só os campos "
            "que mudam. Devolve perfil, modo proteção e a carteira antes e depois."
        ),
        parametros={"type": "object", "properties": {c: _esquema_campo(c) for c in CAMPOS_SIMULAVEIS}},
    )]


def _carteira_resumo(res: Recomendacao) -> dict[str, int]:
    return dict(res.carteira.alocacao)


def simular_cenario(
    alteracoes: dict[str, Any], respostas: dict[str, Any], base: Recomendacao, artefatos: Artefatos
) -> dict[str, Any]:
    """Aplica as alterações (validadas) e roda o assessor de novo. Erros voltam ao modelo como texto."""
    invalidas = []
    validas: dict[str, Any] = {}
    for campo, valor in alteracoes.items():
        p = ui.PERGUNTAS.get(campo)
        if campo not in CAMPOS_SIMULAVEIS or p is None:
            invalidas.append(f"campo desconhecido: {campo}")
            continue
        valores = valor if isinstance(valor, list) else [valor]
        if (p.tipo != "multipla" and isinstance(valor, list)) or any(v not in p.opcoes for v in valores):
            invalidas.append(f"{campo}: valor inválido {valor!r}; opções: {', '.join(p.opcoes)}")
            continue
        validas[campo] = valores if p.tipo == "multipla" else valor
    if invalidas or not validas:
        return {"erro": invalidas or ["nenhuma alteração informada"]}

    q, erros = ui.montar_questionario({**respostas, **validas})
    if erros:
        return {"erro": erros}
    novo = aconselhar(q, artefatos)
    antes, depois = _carteira_resumo(base), _carteira_resumo(novo)
    return {
        "mudancas": {ui.PERGUNTAS[c].texto: (", ".join(ui.PERGUNTAS[c].rotulo(v) for v in validas[c])
                                            if isinstance(validas[c], list) else ui.PERGUNTAS[c].rotulo(validas[c]))
                     for c in validas},
        "perfil_antes": base.carteira.perfil_efetivo,
        "perfil_depois": novo.carteira.perfil_efetivo,
        "modo_protecao_antes": base.carteira.saude.modo_protecao,
        "modo_protecao_depois": novo.carteira.saude.modo_protecao,
        "alertas_depois": novo.carteira.saude.alertas,
        "carteira": [
            {"classe": k, "nome": config.CLASS_INFO[k]["nome"], "antes": antes[k], "depois": depois[k]}
            for k in sorted(depois, key=lambda k: -depois[k])
        ],
        "risco_depois": risco_carteira(novo.carteira)[1],
    }


# ---------------------------------------------------------------------------
# Conversa
# ---------------------------------------------------------------------------
def _historico(historico: list[dict[str, str]]) -> list[Mensagem]:
    msgs = []
    for m in historico[-config.ASSISTANT_MAX_HISTORY:]:
        texto = str(m.get("texto", ""))[: config.ASSISTANT_MAX_QUESTION_CHARS * 4]
        if texto:
            msgs.append(Mensagem("modelo" if m.get("papel") == "assistente" else "usuario", texto))
    return msgs


def conversar(
    respostas: dict[str, Any],
    historico: list[dict[str, str]],
    pergunta: str,
    artefatos: Artefatos,
    provedor: Provedor | None = None,
) -> RespostaConversa:
    """Uma rodada de conversa: pergunta do usuário → (ferramentas) → resposta em texto.

    Levanta ``ValueError`` para entrada inválida e ``AssistenteIndisponivel`` quando
    não há chave ou o modelo falha.
    """
    pergunta = (pergunta or "").strip()
    if not pergunta:
        raise ValueError(["Escreva uma pergunta."])
    if len(pergunta) > config.ASSISTANT_MAX_QUESTION_CHARS:
        raise ValueError([f"Pergunta longa demais (máximo de {config.ASSISTANT_MAX_QUESTION_CHARS} caracteres)."])
    provedor = provedor or obter_provedor()
    if provedor is None:
        raise AssistenteIndisponivel(
            f"O assistente está desativado: defina a variável de ambiente {config.LLM_API_KEY_ENV} com uma chave do Gemini.")
    q, erros = ui.montar_questionario(respostas)
    if erros:
        raise ValueError(erros)

    base = aconselhar(q, artefatos)
    sistema = f"{INSTRUCOES}\n# CONTEXTO\n{contexto(base, respostas)}"
    msgs = [*_historico(historico), Mensagem("usuario", pergunta)]
    tools = ferramentas()
    simulacoes: list[dict[str, Any]] = []

    for _ in range(config.ASSISTANT_MAX_TOOL_ROUNDS):
        r = provedor.gerar(sistema, msgs, tools)
        if not r.chamadas:
            return RespostaConversa(r.texto or "Não consegui formular uma resposta. Pode reformular a pergunta?", simulacoes)
        msgs.append(Mensagem("modelo", r.texto, chamadas=r.chamadas, bruto=r.bruto))
        for chamada in r.chamadas:
            resultado = _executar(chamada, respostas, base, artefatos)
            if "erro" not in resultado:
                simulacoes.append(resultado)
            msgs.append(Mensagem("ferramenta", nome_ferramenta=chamada.nome, resultado=resultado, id_chamada=chamada.id))

    # Limite de rodadas atingido: pede a resposta final sem ferramentas
    r = provedor.gerar(sistema, msgs, [])
    return RespostaConversa(r.texto or "Não consegui concluir a simulação. Tente uma pergunta mais simples.", simulacoes)


def _executar(chamada: ChamadaFerramenta, respostas: dict[str, Any], base: Recomendacao, artefatos: Artefatos) -> dict[str, Any]:
    if chamada.nome == "simular_cenario":
        return simular_cenario(chamada.argumentos, respostas, base, artefatos)
    return {"erro": [f"ferramenta desconhecida: {chamada.nome}"]}
