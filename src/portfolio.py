"""Etapa 6 — Motor de suitability e montagem da carteira.

ESTE MÓDULO NÃO USA MACHINE LEARNING. Ele contém as REGRAS DE NEGÓCIO que
tratam as perguntas sem correspondência no dataset (gasto no cartão, reserva,
objetivo, prazo, tolerância a risco), conforme a premissa do projeto.

Fluxo:
    Questionario ─► calcular_perfil()  → perfil de risco (pontuação documentada)
                 └► avaliar_saude()    → modo proteção (cartão alto / sem reserva)
    perfil + saúde ─► faixas_efetivas() → (mín, máx) % por classe brasileira
    faixas + probabilidades do modelo ─► alocar() → carteira em % (soma 100)

As probabilidades do modelo (Etapa 5) só decidem ONDE, dentro da faixa
permitida pelo perfil, cada classe fica. Elas nunca ultrapassam a faixa.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from src import config
from src.utils import fmt_brl, fmt_num

INVESTMENT_ITEMS: set[str] = set(config.RECOMMEND_ITEMS)


# ---------------------------------------------------------------------------
# Questionário
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Questionario:
    """Respostas do usuário. Valores monetários em BRL por mês (exceto reserva, total)."""

    idade: int
    renda_mensal: float
    gasto_cartao_mensal: float
    reserva_emergencia: float
    objetivo: str
    prazo: str
    tolerancia: str
    produtos: frozenset[str] = field(default_factory=frozenset)  # itens de config.QUESTIONNAIRE_ITEMS
    anos_conta: float = 0.0
    # Perguntas de refinamento (D33); os padrões reproduzem o questionário original
    dependentes: str = "nenhum"
    estabilidade_renda: str = "estavel"
    divida_cara: str = "nao"
    conhecimento: str | None = None          # None = usa só os produtos que já tem
    necessidade_liquidez: str = "nao"

    def __post_init__(self) -> None:
        erros = self.validar()
        if erros:
            raise ValueError(erros)

    def validar(self) -> list[str]:
        """Lista de mensagens de erro (vazia = respostas válidas)."""
        erros: list[str] = []
        if not 18 <= self.idade <= 100:
            erros.append("Idade deve estar entre 18 e 100 anos.")
        if self.renda_mensal <= 0:
            erros.append("Renda mensal deve ser maior que zero.")
        for nome, valor in [("Gasto no cartão", self.gasto_cartao_mensal), ("Reserva de emergência", self.reserva_emergencia), ("Tempo de conta", self.anos_conta)]:
            if valor < 0:
                erros.append(f"{nome} não pode ser negativo.")
        if self.anos_conta > self.idade:
            erros.append("Tempo de conta não pode ser maior que a idade.")
        for pergunta in ("objetivo", "prazo", "tolerancia"):
            opcoes = config.SUITABILITY_POINTS[pergunta]
            if getattr(self, pergunta) not in opcoes:
                erros.append(f"Resposta inválida para '{pergunta}'. Opções: {', '.join(opcoes)}.")
        desconhecidos = set(self.produtos) - set(config.QUESTIONNAIRE_ITEMS)
        if desconhecidos:
            erros.append(f"Produtos desconhecidos: {', '.join(sorted(desconhecidos))}.")
        refinamento = {
            "dependentes": config.DEPENDENTS_OPTIONS,
            "estabilidade_renda": list(config.INCOME_STABILITY_RESERVE_MONTHS),
            "divida_cara": config.EXPENSIVE_DEBT_OPTIONS,
            "necessidade_liquidez": list(config.LIQUIDITY_NEED_BOOST),
        }
        for pergunta, opcoes in refinamento.items():
            if getattr(self, pergunta) not in opcoes:
                erros.append(f"Resposta inválida para '{pergunta}'. Opções: {', '.join(opcoes)}.")
        if self.conhecimento is not None and self.conhecimento not in config.KNOWLEDGE_TO_EXPERIENCE:
            erros.append(f"Resposta inválida para 'conhecimento'. Opções: {', '.join(config.KNOWLEDGE_TO_EXPERIENCE)}.")
        return erros


def experiencia_por_produtos(produtos: frozenset[str] | set[str]) -> str:
    """Experiência inferida dos produtos que o usuário já tem (decisão D16).

    Mais objetivo que uma autoavaliação ("me considero experiente"):
    nenhum investimento → nenhuma; só poupança/CDB → básica;
    fundos/previdência → intermediária; ações → avançada.
    """
    if "acoes" in produtos:
        return "avancada"
    if produtos & {"fundos", "previdencia"}:
        return "intermediaria"
    if produtos & {"poupanca", "deposito"}:
        return "basica"
    return "nenhuma"


def experiencia_efetiva(q: Questionario) -> str:
    """Menor nível entre o inferido dos produtos e o conhecimento declarado (prudência, D33).

    Quem tem ações mas diz não entender do assunto é tratado pelo nível declarado;
    quem diz ser avançado sem ter investimentos é tratado pelo que já tem.
    """
    pelos_produtos = experiencia_por_produtos(q.produtos)
    if q.conhecimento is None:
        return pelos_produtos
    declarada = config.KNOWLEDGE_TO_EXPERIENCE[q.conhecimento]
    return min(pelos_produtos, declarada, key=config.EXPERIENCE_ORDER.index)


def faixa_idade(idade: int) -> str:
    """Faixa usada na pontuação: mais jovem = mais tempo para se recuperar de perdas."""
    if idade < 35:
        return "ate_34"
    if idade < 55:
        return "35_a_54"
    return "55_ou_mais"


# ---------------------------------------------------------------------------
# Perfil de risco
# ---------------------------------------------------------------------------
@dataclass
class PerfilRisco:
    perfil: str
    pontos: int
    pontos_max: int
    perfil_pela_soma: str
    detalhamento: dict[str, tuple[str, int]]   # dimensão → (resposta, pontos)
    limitado_por: list[str]                    # regras de teto aplicadas


def _perfil_por_pontos(pontos: int) -> str:
    for lo, hi, perfil in config.RISK_PROFILE_BANDS:
        if lo <= pontos <= hi:
            return perfil
    raise ValueError(f"Pontuação fora das faixas: {pontos}")


def _mais_conservador(a: str, b: str) -> str:
    return min(a, b, key=config.RISK_PROFILES.index)


def calcular_perfil(q: Questionario) -> PerfilRisco:
    """Soma os pontos de cada dimensão e aplica os tetos (a resposta mais restritiva prevalece).

    Ex.: quem "venderia tudo" numa queda de 20% é conservador, mesmo que a
    soma dos pontos indique arrojado. A tolerância real a perdas manda.
    """
    respostas = {
        "prazo": q.prazo,
        "tolerancia": q.tolerancia,
        "objetivo": q.objetivo,
        "experiencia": experiencia_efetiva(q),
        "idade": faixa_idade(q.idade),
    }
    detalhamento = {dim: (resp, config.SUITABILITY_POINTS[dim][resp]) for dim, resp in respostas.items()}
    pontos = sum(p for _, p in detalhamento.values())
    pontos_max = sum(max(v.values()) for v in config.SUITABILITY_POINTS.values())

    # Tetos: respostas da pontuação + número de dependentes (capacidade de suportar perdas)
    tetos = [(f"{DIMENSOES_CURTAS[dim]}: {RESPOSTAS_LEGIVEIS.get(resp, resp)}", teto)
             for (dim, resp), teto in config.PROFILE_CAPS.items() if respostas[dim] == resp]
    if q.dependentes in config.DEPENDENTS_CAP:
        tetos.append(("3 ou mais dependentes", config.DEPENDENTS_CAP[q.dependentes]))

    perfil_soma = _perfil_por_pontos(pontos)
    perfil, limitado_por = perfil_soma, []
    for motivo, teto in tetos:
        if config.RISK_PROFILES.index(teto) < config.RISK_PROFILES.index(perfil):
            perfil = _mais_conservador(perfil, teto)
            limitado_por.append(f"{motivo} → no máximo {teto}")
    return PerfilRisco(perfil, pontos, pontos_max, perfil_soma, detalhamento, limitado_por)


# ---------------------------------------------------------------------------
# Saúde financeira
# ---------------------------------------------------------------------------
@dataclass
class SaudeFinanceira:
    comprometimento_cartao: float   # gasto no cartão / renda
    meses_reserva: float            # reserva / renda mensal
    reserva_alvo: float
    falta_reserva: float
    cartao_alto: bool
    sem_reserva: bool
    tem_emprestimo: bool
    alertas: list[str]
    meses_alvo: int = config.EMERGENCY_RESERVE_MONTHS
    divida_cara: bool = False

    @property
    def modo_protecao(self) -> bool:
        """Cartão alto, reserva insuficiente OU dívida cara → base financeira antes de qualquer risco."""
        return self.cartao_alto or self.sem_reserva or self.divida_cara


def avaliar_saude(q: Questionario) -> SaudeFinanceira:
    """Regras de saúde financeira que vêm ANTES do perfil de risco.

    A reserva é medida em meses de RENDA, porque o questionário não pergunta o
    custo de vida total. Isso é conservador: o custo de vida costuma ser menor
    que a renda, então a reserva-alvo fica maior. Renda variável exige uma
    reserva maior (12 meses), porque os meses sem renda são mais prováveis.
    """
    meses_alvo = config.INCOME_STABILITY_RESERVE_MONTHS[q.estabilidade_renda]
    comprometimento = q.gasto_cartao_mensal / q.renda_mensal
    meses = q.reserva_emergencia / q.renda_mensal
    alvo = meses_alvo * q.renda_mensal
    falta = max(0.0, alvo - q.reserva_emergencia)
    cartao_alto = comprometimento > config.CARD_SPEND_LIMIT
    sem_reserva = meses < meses_alvo
    divida_cara = q.divida_cara == "sim"
    tem_emprestimo = "emprestimo" in q.produtos

    alertas = []
    if divida_cara:
        alertas.append(
            "Você tem dívida no rotativo do cartão ou no cheque especial. Quitá-la vem antes de investir: "
            "os juros dessas dívidas superam de longe o rendimento de qualquer aplicação."
        )
    if cartao_alto:
        alertas.append(
            f"Seu gasto no cartão compromete cerca de {comprometimento:.0%} da renda (referência: até "
            f"{config.CARD_SPEND_LIMIT:.0%}). Acima disso, um imprevisto pode levar ao rotativo."
        )
    if sem_reserva:
        motivo = "" if q.estabilidade_renda == "estavel" else " (sua renda varia, por isso a meta é maior)"
        situacao = ("Você ainda não tem reserva de emergência" if meses == 0
                    else f"Sua reserva cobre cerca de {fmt_num(meses, 1)} meses de renda")
        alertas.append(
            f"{situacao}; o recomendado é {meses_alvo} meses{motivo}. "
            f"Faltam cerca de {fmt_brl(falta)}. Priorize completá-la em aplicações de liquidez diária."
        )
    if tem_emprestimo:
        alertas.append("Você tem empréstimo/financiamento: compare a taxa da dívida com o retorno esperado antes de investir.")
    return SaudeFinanceira(comprometimento, meses, alvo, falta, cartao_alto, sem_reserva, tem_emprestimo, alertas,
                           meses_alvo, divida_cara)


# ---------------------------------------------------------------------------
# Carteira
# ---------------------------------------------------------------------------
Faixas = dict[str, tuple[float, float]]


def validar_faixas(faixas: Faixas) -> None:
    """Garante que existe ao menos uma carteira válida (Σmín ≤ 100 ≤ Σmáx)."""
    soma_min = sum(lo for lo, _ in faixas.values())
    soma_max = sum(hi for _, hi in faixas.values())
    if soma_min > 100 or soma_max < 100:
        raise ValueError(f"Faixas inviáveis: Σmín={soma_min}, Σmáx={soma_max}")
    for classe, (lo, hi) in faixas.items():
        if not 0 <= lo <= hi <= 100:
            raise ValueError(f"Faixa inválida para {classe}: ({lo}, {hi})")


def faixas_efetivas(
    perfil: PerfilRisco, saude: SaudeFinanceira, necessidade_liquidez: str = "nao"
) -> tuple[str, Faixas]:
    """Faixas do perfil; no modo proteção, perfil conservador com liquidez reforçada.

    Modo proteção: liquidez ≥ PROTECTION_LIQUIDITY_MIN e classes de risco
    (multimercado, ações) e de baixa liquidez (previdência) zeradas até que a
    reserva esteja completa e o cartão sob controle.

    Quem pode precisar do dinheiro antes do prazo ganha pontos extras no mínimo
    de liquidez (D33). Se os mínimos passarem de 100%, a renda fixa cede primeiro.
    """
    perfil_ef = "conservador" if saude.modo_protecao else perfil.perfil
    faixas: Faixas = {c: tuple(map(float, b)) for c, b in config.ALLOCATION_BANDS[perfil_ef].items()}
    if saude.modo_protecao:
        faixas["liquidez"] = (max(faixas["liquidez"][0], config.PROTECTION_LIQUIDITY_MIN), 100.0)
        for classe in ("multimercado", "acoes", "previdencia"):
            faixas[classe] = (0.0, 0.0)

    extra = config.LIQUIDITY_NEED_BOOST[necessidade_liquidez]
    if extra:
        lo, hi = faixas["liquidez"]
        faixas["liquidez"] = (lo + extra, max(hi, lo + extra))
        excesso = sum(lo for lo, _ in faixas.values()) - 100
        for classe in ("renda_fixa", "multimercado", "acoes", "previdencia"):
            if excesso <= 0:
                break
            lo_c, hi_c = faixas[classe]
            corte = min(excesso, lo_c)
            faixas[classe] = (lo_c - corte, hi_c)
            excesso -= corte
    validar_faixas(faixas)
    return perfil_ef, faixas


def afinidade_por_classe(probabilidades: dict[str, float] | None) -> dict[str, float]:
    """Converte P(item) do modelo em afinidade por classe brasileira (mapeamento explícito).

    Sem modelo (None), todas as classes têm a mesma afinidade.
    """
    classes = list(config.BR_ASSET_CLASSES)
    if probabilidades is None:
        return {c: 1.0 for c in classes}
    afinidade = {c: 0.0 for c in classes}
    for item, classe in config.ITEM_TO_BR_CLASS.items():
        afinidade[classe] = max(afinidade[classe], float(probabilidades.get(item, 0.0)))
    return afinidade


def alocar(faixas: Faixas, afinidade: dict[str, float]) -> dict[str, int]:
    """Distribui 100% respeitando as faixas, com o espaço livre proporcional à afinidade.

    1. Cada classe começa no seu mínimo.
    2. O que sobra é repartido proporcionalmente à afinidade (com piso
       ``MODEL_AFFINITY_FLOOR``), sem passar do máximo. O excedente de quem
       atinge o teto é redistribuído entre os demais ("water-filling").
    3. Arredondamento para inteiros pelo maior resto, mantendo soma 100.
    """
    validar_faixas(faixas)
    aloc = {c: lo for c, (lo, _) in faixas.items()}
    restante = 100.0 - sum(aloc.values())
    ativos = {c for c, (lo, hi) in faixas.items() if hi > lo}
    while restante > 1e-9 and ativos:
        pesos = {c: max(afinidade.get(c, 0.0), config.MODEL_AFFINITY_FLOOR) for c in ativos}
        total = sum(pesos.values())
        distribuido = 0.0
        for c in list(ativos):
            espaco = faixas[c][1] - aloc[c]
            add = min(restante * pesos[c] / total, espaco)
            aloc[c] += add
            distribuido += add
            if faixas[c][1] - aloc[c] <= 1e-9:
                ativos.discard(c)
        restante -= distribuido
    if restante > 1e-6:
        raise ValueError("Não foi possível distribuir 100% dentro das faixas.")

    # Maior resto: pisos inteiros e +1 para as maiores frações até somar 100
    pisos = {c: math.floor(v + 1e-9) for c, v in aloc.items()}
    faltam = 100 - sum(pisos.values())
    for c in sorted(aloc, key=lambda c: aloc[c] - pisos[c], reverse=True)[:faltam]:
        pisos[c] += 1
    return pisos


def alocar_sem_residuos(faixas: Faixas, afinidade: dict[str, float]) -> dict[str, int]:
    """Como :func:`alocar`, mas zera classes OPCIONAIS (mínimo 0) com fatia residual.

    1% em previdência não tem efeito prático e só complica a carteira. As
    classes abaixo de ``MIN_ALLOCATION_PCT`` são removidas e a alocação é
    refeita; se isso tornar as faixas inviáveis, mantém o resultado original.
    """
    aloc = alocar(faixas, afinidade)
    residuais = [c for c, v in aloc.items() if 0 < v < config.MIN_ALLOCATION_PCT and faixas[c][0] == 0]
    if not residuais:
        return aloc
    ajustadas = {**faixas, **{c: (0.0, 0.0) for c in residuais}}
    try:
        return alocar(ajustadas, afinidade)
    except ValueError:
        return aloc


@dataclass
class Carteira:
    perfil: PerfilRisco
    saude: SaudeFinanceira
    perfil_efetivo: str
    faixas: Faixas
    afinidade: dict[str, float]
    alocacao: dict[str, int]
    liquidez_extra: int = 0   # pontos extras no mínimo de liquidez (necessidade de resgate)

    def classes_permitidas(self) -> set[str]:
        return {c for c, (_, hi) in self.faixas.items() if hi > 0}


def montar_carteira(q: Questionario, probabilidades: dict[str, float] | None = None) -> Carteira:
    """Pipeline completo de regras: perfil → saúde → faixas → alocação."""
    perfil = calcular_perfil(q)
    saude = avaliar_saude(q)
    perfil_ef, faixas = faixas_efetivas(perfil, saude, q.necessidade_liquidez)
    afinidade = afinidade_por_classe(probabilidades)
    return Carteira(perfil, saude, perfil_ef, faixas, afinidade, alocar_sem_residuos(faixas, afinidade),
                    config.LIQUIDITY_NEED_BOOST[q.necessidade_liquidez])


# ---------------------------------------------------------------------------
# Leitura da carteira em linguagem simples (D35)
# ---------------------------------------------------------------------------
RISK_CLASSES: tuple[str, ...] = ("multimercado", "acoes", "previdencia")


def risco_carteira(carteira: Carteira) -> tuple[float, str]:
    """Risco médio ponderado (1 = muito baixo … 4 = alto) e seu rótulo."""
    nota = sum(pct * config.CLASS_INFO[c]["risco"] for c, pct in carteira.alocacao.items()) / 100
    rotulo = next(r for limite, r in config.PORTFOLIO_RISK_BANDS if nota < limite)
    return nota, rotulo


def por_mil(pct: int) -> int:
    """Quanto vai para a classe a cada R$ 1.000 investidos."""
    return pct * 10


def explicar_classe(carteira: Carteira, classe: str) -> str:
    """Por que a classe ficou com essa porcentagem (ou ficou de fora), em uma ou duas frases."""
    lo, hi = carteira.faixas[classe]
    pct = carteira.alocacao[classe]
    if hi == 0:
        if carteira.saude.modo_protecao and classe in RISK_CLASSES:
            return ("Fica de fora por enquanto: antes de investir em algo que oscila ou tem resgate difícil, "
                    "é preciso organizar a base financeira.")
        return "Não faz parte da carteira do seu perfil."
    if pct == 0:
        return f"Ficou de fora: a fatia seria menor que {config.MIN_ALLOCATION_PCT}%, pequena demais para fazer diferença."

    frases = [f"No perfil {carteira.perfil_efetivo}, esta classe fica entre {lo:.0f}% e {hi:.0f}%."]
    if classe == "liquidez" and carteira.liquidez_extra:
        frases.append(f"O mínimo subiu {carteira.liquidez_extra} pontos porque você pode precisar do dinheiro antes do prazo.")
    if pct <= lo + 0.5:
        frases.append("Ficou no mínimo: entre clientes parecidos com você, esta classe é pouco comum.")
    elif pct >= hi - 0.5:
        frases.append("Ficou no máximo: é uma das classes mais comuns entre clientes parecidos com você.")
    else:
        frases.append("Ficou no meio da faixa, conforme o quanto clientes parecidos com você usam esta classe.")
    return " ".join(frases)


def resumo_simples(carteira: Carteira) -> list[str]:
    """Três frases que respondem: quem sou, qual a prioridade, o que fazer com o dinheiro."""
    p, s = carteira.perfil, carteira.saude
    perfil = carteira.perfil_efetivo
    frase_perfil = f"Seu perfil é **{perfil}**: {config.PROFILE_DESCRIPTIONS[perfil]}"
    if s.modo_protecao and p.perfil != perfil:
        frase_perfil += f" Pelas suas respostas você seria **{p.perfil}**, mas seguimos o conservador até organizar a base."

    if s.modo_protecao:
        tarefas = []
        if s.divida_cara:
            tarefas.append("quitar a dívida cara")
        if s.cartao_alto:
            tarefas.append("reduzir o gasto no cartão")
        if s.sem_reserva:
            tarefas.append(f"completar a reserva (faltam cerca de {fmt_brl(s.falta_reserva)})")
        lista = tarefas[0] if len(tarefas) == 1 else ", ".join(tarefas[:-1]) + " e " + tarefas[-1]
        frase_prioridade = f"Sua prioridade agora é organizar a base: {lista}."
    else:
        frase_prioridade = "Sua base financeira está em ordem: reserva adequada, sem dívida cara e cartão sob controle."

    principais = sorted(((c, v) for c, v in carteira.alocacao.items() if v > 0), key=lambda kv: -kv[1])[:2]
    _, rotulo_risco = risco_carteira(carteira)
    # Minúscula só na 1ª letra, para preservar siglas ("Ações / ETFs" → "ações / ETFs")
    nome = lambda c: config.CLASS_INFO[c]["nome"][0].lower() + config.CLASS_INFO[c]["nome"][1:]  # noqa: E731
    destaque = " e ".join(f"{v}% em {nome(c)}" for c, v in principais)
    frase_carteira = f"A carteira sugerida concentra {destaque}. Risco estimado: **{rotulo_risco.lower()}**."
    return [frase_perfil, frase_prioridade, frase_carteira]


def proximos_passos(carteira: Carteira) -> list[str]:
    """Lista de ações práticas, na ordem em que devem ser feitas."""
    s = carteira.saude
    passos = []
    if s.divida_cara:
        passos.append("Quite primeiro o rotativo do cartão ou o cheque especial; se preciso, troque por um empréstimo mais barato.")
    if s.cartao_alto:
        passos.append(f"Traga o gasto no cartão para menos de {config.CARD_SPEND_LIMIT:.0%} da renda.")
    if s.sem_reserva:
        passos.append(f"Junte cerca de {fmt_brl(s.falta_reserva)} em liquidez diária, até cobrir {s.meses_alvo} meses de renda.")
    if s.modo_protecao:
        passos.append("Refaça o questionário quando esses pontos estiverem resolvidos para liberar ações, multimercado e previdência.")
    else:
        passos.append(f"Mantenha a reserva de emergência ({s.meses_alvo} meses de renda) separada, em liquidez diária.")
        passos.append("Distribua cada novo aporte seguindo as porcentagens da carteira.")
        passos.append("A cada 6 a 12 meses, confira se alguma classe saiu da faixa e volte às porcentagens sugeridas.")
    if s.tem_emprestimo:
        passos.append("Compare a taxa do seu empréstimo com o rendimento esperado: amortizar pode valer mais que investir.")
    if not s.modo_protecao:  # no modo proteção já há um "refaça o questionário" acima
        passos.append("Refaça o questionário se sua renda, seus objetivos ou o número de dependentes mudarem.")
    return passos


# ---------------------------------------------------------------------------
# Explicação em linguagem simples (template determinístico e auditável)
# ---------------------------------------------------------------------------
RESPOSTAS_LEGIVEIS: dict[str, str] = {
    "ate_1_ano": "até 1 ano", "1_a_3_anos": "de 1 a 3 anos", "3_a_5_anos": "de 3 a 5 anos", "mais_de_5_anos": "mais de 5 anos",
    "venderia_tudo": "venderia tudo", "venderia_parte": "venderia uma parte", "manteria": "manteria", "compraria_mais": "compraria mais",
    "reserva": "montar reserva", "comprar_bem": "comprar um bem", "renda_extra": "gerar renda extra",
    "aposentadoria": "aposentadoria", "crescer_patrimonio": "fazer o patrimônio crescer",
    "nenhuma": "nenhuma", "basica": "básica", "intermediaria": "intermediária", "avancada": "avançada",
    "ate_34": "até 34 anos", "35_a_54": "35 a 54 anos", "55_ou_mais": "55 anos ou mais",
    # perguntas de refinamento
    "nenhum": "nenhum", "1_a_2": "1 ou 2 pessoas", "3_ou_mais": "3 ou mais pessoas",
    "estavel": "estável (CLT, servidor, aposentado)", "variavel": "variável (autônomo, comissão, empresa)",
    "sem_renda_fixa": "não tenho renda fixa",
    "nao": "não", "talvez": "talvez", "sim": "sim",
    "basico": "básico: conheço poupança e CDB", "intermediario": "intermediário: entendo fundos e Tesouro",
    "avancado": "avançado: acompanho ações e o mercado",
}
DIMENSOES: dict[str, str] = {
    "prazo": "Prazo", "tolerancia": "Reação a uma queda de 20%", "objetivo": "Objetivo",
    "experiencia": "Experiência (produtos que você tem e conhecimento declarado)", "idade": "Faixa etária",
}
DIMENSOES_CURTAS: dict[str, str] = {
    "prazo": "prazo", "tolerancia": "numa queda de 20%", "objetivo": "objetivo",
    "experiencia": "experiência", "idade": "idade",
}


def _frase_fatores(fatores: list[dict]) -> str:
    a_favor = [f["rotulo"] for f in fatores if f["contribuicao"] > 0]
    contra = [f["rotulo"] for f in fatores if f["contribuicao"] < 0]
    partes = []
    if a_favor:
        partes.append("pesou a favor: " + ", ".join(a_favor))
    if contra:
        partes.append("pesou contra: " + ", ".join(contra))
    return "; ".join(partes)


def gerar_explicacao(
    carteira: Carteira,
    cluster_nome: str | None = None,
    produtos: list[dict] | None = None,
) -> str:
    """Texto em Markdown explicando perfil, alertas, carteira e produtos sugeridos.

    ``produtos``: lista de dicts com ``rotulo``, ``prob`` e ``fatores`` (saída do SHAP).
    """
    p, s = carteira.perfil, carteira.saude
    linhas = ["### Em resumo", *[f"- {frase}" for frase in resumo_simples(carteira)]]
    linhas.append(f"\n### Seu perfil: **{carteira.perfil_efetivo.capitalize()}**")
    linhas.append(f"Você somou **{p.pontos} de {p.pontos_max} pontos** no questionário de suitability:")
    linhas += [f"- {DIMENSOES[d]}: {RESPOSTAS_LEGIVEIS.get(r, r)} → {pts} pt" for d, (r, pts) in p.detalhamento.items()]
    if p.limitado_por:
        linhas.append(
            f"A soma indicaria **{p.perfil_pela_soma}**, mas algumas respostas limitam o risco "
            f"({'; '.join(p.limitado_por)}). Seguimos sempre a resposta mais prudente."
        )
    if s.modo_protecao:
        linhas.append(
            "**Antes de investir com risco, organize a base financeira.** Por isso a carteira abaixo "
            "concentra-se em liquidez e renda fixa e deixa de fora ações, multimercado e previdência:"
        )
    linhas += [f"- ⚠️ {a}" for a in s.alertas]

    if cluster_nome:
        linhas.append(f"\nPelos seus dados, você se parece com o grupo **\"{cluster_nome}\"** de clientes.")

    linhas.append("\n### Carteira sugerida (de cada R$ 1.000 investidos)")
    for classe, pct in sorted(carteira.alocacao.items(), key=lambda kv: -kv[1]):
        if pct > 0:
            info = config.CLASS_INFO[classe]
            linhas.append(f"- **{pct}% · R$ {por_mil(pct)} em {info['nome']}**: {info['papel']} {explicar_classe(carteira, classe)}")
    fora = [c for c, pct in carteira.alocacao.items() if pct == 0]
    if fora:
        linhas.append("- Fora da carteira: " + ", ".join(config.CLASS_INFO[c]["nome"] for c in fora) + ". "
                      + explicar_classe(carteira, fora[0]))

    linhas.append("\n### Próximos passos")
    linhas += [f"{i}. {passo}" for i, passo in enumerate(proximos_passos(carteira), 1)]

    if produtos:
        linhas.append("\n### Próximos produtos para conhecer")
        for prod in produtos:
            motivo = _frase_fatores(prod.get("fatores", []))
            linhas.append(f"- **{prod['rotulo']}**: cerca de {prod['prob']:.0%} dos clientes com perfil parecido têm" + (f" ({motivo})." if motivo else "."))
    elif produtos is not None and not s.modo_protecao:
        linhas.append(
            "\n### Próximos produtos\nVocê já tem os produtos mais comuns para o seu perfil. "
            "O foco agora é manter a carteira dentro das faixas acima (rebalanceamento)."
        )
    linhas.append(f"\n> {config.DISCLAIMER}")
    return "\n".join(linhas)
