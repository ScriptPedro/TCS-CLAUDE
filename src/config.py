"""Configuração central do projeto Assessor de Investimentos Virtual.

Toda constante usada pelos scripts (caminhos, colunas, sementes, premissas de
negócio) mora aqui. Nenhum outro módulo deve ter valores "mágicos" hardcoded.
"""

from __future__ import annotations

from pathlib import Path

# ---------------------------------------------------------------------------
# Caminhos
# ---------------------------------------------------------------------------
ROOT_DIR: Path = Path(__file__).resolve().parents[1]
DATA_DIR: Path = ROOT_DIR / "data"
RAW_DIR: Path = DATA_DIR / "raw"
PROCESSED_DIR: Path = DATA_DIR / "processed"
MODELS_DIR: Path = ROOT_DIR / "models"
REPORTS_DIR: Path = ROOT_DIR / "reports"
FIGURES_DIR: Path = ROOT_DIR / "docs" / "figures"

RAW_FILE: Path = RAW_DIR / "train_ver2.csv"
PROCESSED_FILE: Path = PROCESSED_DIR / "santander_50k.parquet"
QUALITY_REPORT_FILE: Path = REPORTS_DIR / "qualidade_dados.md"
# Estatísticas de limpeza (medianas, limites, faixas) reutilizadas pelo app
PREP_STATS_FILE: Path = MODELS_DIR / "prep_stats.json"

# ---------------------------------------------------------------------------
# Kaggle
# ---------------------------------------------------------------------------
KAGGLE_COMPETITION: str = "santander-product-recommendation"
KAGGLE_FILE: str = "train_ver2.csv.zip"

# ---------------------------------------------------------------------------
# Reprodutibilidade e amostragem
# ---------------------------------------------------------------------------
RANDOM_STATE: int = 42
SNAPSHOT_DATE: str = "2016-05-28"  # último mês disponível no train_ver2.csv
SAMPLE_SIZE: int = 50_000  # clientes ÚNICOS (1 linha por ncodpers)
STRATIFY_COL: str = "segmento"
CHUNK_SIZE: int = 500_000  # linhas por chunk na leitura do CSV

# ---------------------------------------------------------------------------
# Colunas demográficas / de relacionamento
# ---------------------------------------------------------------------------
ID_COL: str = "ncodpers"
DATE_COL: str = "fecha_dato"
DEMOGRAPHIC_COLS: list[str] = [
    "age",
    "renta",
    "antiguedad",
    "sexo",
    "segmento",
    "ind_actividad_cliente",
    "ind_nuevo",
    "canal_entrada",  # opcional; pode ser descartada na modelagem
]

# ---------------------------------------------------------------------------
# Produtos: nomes reais das 24 colunas do train_ver2.csv agrupados por classe.
# Os nomes serão conferidos contra o cabeçalho do arquivo na Etapa 2.
# ---------------------------------------------------------------------------
PRODUCT_GROUPS: dict[str, list[str]] = {
    "liquidez": [
        "ind_cco_fin_ult1",    # conta corrente
        "ind_cno_fin_ult1",    # conta salário (payroll account) — não estava na lista original
        "ind_ecue_fin_ult1",   # conta digital (e-account)
        "ind_ctop_fin_ult1",   # conta "particular"
        "ind_ctpp_fin_ult1",   # conta "particular plus"
        "ind_ctma_fin_ult1",   # conta "más particular"
        "ind_ctju_fin_ult1",   # conta júnior
        "ind_nomina_ult1",     # recebimento de salário
        "ind_nom_pens_ult1",   # recebimento de pensão
        "ind_recibo_ult1",     # débito automático
    ],
    "renda_fixa": [
        "ind_ahor_fin_ult1",   # poupança
        "ind_deco_fin_ult1",   # depósito curto prazo
        "ind_deme_fin_ult1",   # depósito médio prazo
        "ind_dela_fin_ult1",   # depósito longo prazo
    ],
    "renda_variavel": [
        "ind_fond_fin_ult1",   # fundos
        "ind_valo_fin_ult1",   # valores mobiliários
        "ind_cder_fin_ult1",   # derivativos
    ],
    "longo_prazo": [
        "ind_plan_fin_ult1",   # previdência
    ],
    # Crédito: usado APENAS como sinal de perfil, nunca recomendado.
    "credito": [
        "ind_tjcr_fin_ult1",   # cartão de crédito
        "ind_pres_fin_ult1",   # empréstimo
        "ind_hip_fin_ult1",    # hipoteca
        "ind_viv_fin_ult1",    # financiamento habitacional
        "ind_aval_fin_ult1",   # aval/garantias
        "ind_reca_fin_ult1",   # conta de impostos (taxes) — tratada como sinal
    ],
}

PRODUCT_COLS: list[str] = [c for cols in PRODUCT_GROUPS.values() for c in cols]
NON_RECOMMENDABLE_GROUPS: tuple[str, ...] = ("credito",)
# Classes que contam como "investimento" (além da conta/liquidez)
INVESTMENT_GROUPS: tuple[str, ...] = ("renda_fixa", "renda_variavel", "longo_prazo")

# Rótulos legíveis para gráficos e para a interface
GROUP_LABELS: dict[str, str] = {
    "liquidez": "Liquidez / conta",
    "renda_fixa": "Renda fixa",
    "renda_variavel": "Renda variável",
    "longo_prazo": "Previdência",
    "credito": "Crédito",
}
PRODUCT_LABELS: dict[str, str] = {
    "ind_cco_fin_ult1": "Conta corrente",
    "ind_cno_fin_ult1": "Conta salário",
    "ind_ecue_fin_ult1": "Conta digital",
    "ind_ctop_fin_ult1": "Conta particular",
    "ind_ctpp_fin_ult1": "Conta particular plus",
    "ind_ctma_fin_ult1": "Conta más particular",
    "ind_ctju_fin_ult1": "Conta júnior",
    "ind_nomina_ult1": "Folha de pagamento",
    "ind_nom_pens_ult1": "Pensão",
    "ind_recibo_ult1": "Débito automático",
    "ind_ahor_fin_ult1": "Poupança",
    "ind_deco_fin_ult1": "Depósito curto prazo",
    "ind_deme_fin_ult1": "Depósito médio prazo",
    "ind_dela_fin_ult1": "Depósito longo prazo",
    "ind_fond_fin_ult1": "Fundos",
    "ind_valo_fin_ult1": "Valores mobiliários",
    "ind_cder_fin_ult1": "Derivativos",
    "ind_plan_fin_ult1": "Previdência",
    "ind_tjcr_fin_ult1": "Cartão de crédito",
    "ind_pres_fin_ult1": "Empréstimo",
    "ind_hip_fin_ult1": "Hipoteca",
    "ind_viv_fin_ult1": "Financ. habitacional",
    "ind_aval_fin_ult1": "Aval / garantias",
    "ind_reca_fin_ult1": "Conta de impostos",
}

# Colunas lidas do CSV bruto (todo o resto é descartado já na leitura)
USECOLS: list[str] = [DATE_COL, ID_COL, *DEMOGRAPHIC_COLS, *PRODUCT_COLS]

# ---------------------------------------------------------------------------
# Regras de limpeza (Etapa 2)
# ---------------------------------------------------------------------------
AGE_MIN: int = 18
AGE_MAX: int = 100
WINSOR_LOWER_Q: float = 0.01
WINSOR_UPPER_Q: float = 0.99
AGE_BINS: list[int] = [18, 25, 35, 45, 55, 65, 101]
AGE_LABELS: list[str] = ["18-24", "25-34", "35-44", "45-54", "55-64", "65+"]

# Rótulo único para categorias ausentes (não descartamos clientes por isso)
UNKNOWN_LABEL: str = "desconhecido"
# Tokens que o CSV usa para "sem valor" (além de célula vazia)
NA_TOKENS: list[str] = ["", "NA", "NaN", "nan"]
# Colunas lidas como texto e convertidas para número após o strip()
NUMERIC_TEXT_COLS: list[str] = [
    "age", "antiguedad", "renta", "ind_actividad_cliente", "ind_nuevo",
]
CATEGORICAL_COLS: list[str] = ["sexo", "segmento", "canal_entrada"]
SEGMENT_MAP: dict[str, str] = {
    "01 - TOP": "top",
    "02 - PARTICULARES": "particulares",
    "03 - UNIVERSITARIO": "universitario",
}

# ---------------------------------------------------------------------------
# Renda: estratégia escolhida = QUANTIS (faixas relativas), não conversão.
# A taxa abaixo existe só para exibição ilustrativa e está documentada como premissa.
# ---------------------------------------------------------------------------
INCOME_STRATEGY: str = "quantis"  # "quantis" | "conversao"
N_INCOME_QUANTILES: int = 5
INCOME_QUANTILE_LABELS: list[str] = ["muito_baixa", "baixa", "media", "alta", "muito_alta"]
EUR_TO_BRL_RATE: float = 6.00  # premissa ilustrativa; ver docs/decisoes.md (D3)

# ---------------------------------------------------------------------------
# Segmentação (Etapa 4)
# ---------------------------------------------------------------------------
SEGMENTATION_MODEL_FILE: Path = MODELS_DIR / "segmentation.joblib"
CLUSTERED_FILE: Path = PROCESSED_DIR / "santander_50k_clusters.parquet"
SEGMENTATION_REPORT_FILE: Path = REPORTS_DIR / "segmentacao.md"

# Features do clustering. sexo fica de fora por decisão ética (D11);
# produtos individuais entram agregados por classe (D13).
# Contínuas → StandardScaler; binárias/contagens → MinMax 0–1 (D14).
SEG_CONTINUOUS_FEATURES: list[str] = ["age", "renta_log", "antiguedad"]
SEG_BOUNDED_FEATURES: list[str] = [
    "ind_actividad_cliente",
    *[f"n_{g}" for g in PRODUCT_GROUPS],
]
SEG_NUMERIC_FEATURES: list[str] = [*SEG_CONTINUOUS_FEATURES, *SEG_BOUNDED_FEATURES]
SEG_CATEGORICAL_FEATURES: list[str] = ["segmento"]

K_RANGE: range = range(2, 11)          # k avaliados (cotovelo/silhouette)
K_MIN_BUSINESS: int = 4                # menos que isso = segmentos genéricos demais
K_MAX_BUSINESS: int = 8                # mais que isso = difícil de nomear e explicar
KMEANS_N_INIT: int = 10
SILHOUETTE_SAMPLE: int = 10_000        # silhouette é O(n²): calculado numa amostra
GMM_REG_COVAR: float = 1e-3            # estabiliza covariâncias com colunas 0/1
# Nomes revisados por humanos após ver o perfil real ({id_cluster: "nome"}).
# Vazio = usa os nomes automáticos gerados por regras.
CLUSTER_NAME_OVERRIDES: dict[int, str] = {}
STABILITY_RUNS: int = 5
STABILITY_FRACTION: float = 0.8

# ---------------------------------------------------------------------------
# Recomendação (Etapa 5)
# ---------------------------------------------------------------------------
REC_MODEL_FILE: Path = MODELS_DIR / "recommender.joblib"
REC_REPORT_FILE: Path = REPORTS_DIR / "recomendacao.md"

# Ponte questionário ↔ dataset (D16): cada item da pergunta "Quais destes
# produtos você já tem?" corresponde a um conjunto de produtos Santander.
QUESTIONNAIRE_ITEMS: dict[str, list[str]] = {
    "conta": [
        "ind_cco_fin_ult1", "ind_cno_fin_ult1", "ind_ecue_fin_ult1", "ind_ctop_fin_ult1",
        "ind_ctpp_fin_ult1", "ind_ctma_fin_ult1", "ind_ctju_fin_ult1",
    ],
    "poupanca": ["ind_ahor_fin_ult1"],
    "deposito": ["ind_deco_fin_ult1", "ind_deme_fin_ult1", "ind_dela_fin_ult1"],
    "fundos": ["ind_fond_fin_ult1"],
    "acoes": ["ind_valo_fin_ult1", "ind_cder_fin_ult1"],
    "previdencia": ["ind_plan_fin_ult1"],
    "cartao": ["ind_tjcr_fin_ult1"],
    "emprestimo": ["ind_pres_fin_ult1", "ind_hip_fin_ult1", "ind_viv_fin_ult1"],
}
QUESTIONNAIRE_LABELS: dict[str, str] = {
    "conta": "Conta corrente / digital",
    "poupanca": "Poupança",
    "deposito": "CDB / depósito a prazo",
    "fundos": "Fundos de investimento",
    "acoes": "Ações / valores mobiliários",
    "previdencia": "Previdência privada",
    "cartao": "Cartão de crédito",
    "emprestimo": "Empréstimo / financiamento",
}
# Itens que o modelo pode RECOMENDAR (só investimentos; nunca crédito — D5)
RECOMMEND_ITEMS: list[str] = ["poupanca", "deposito", "fundos", "acoes", "previdencia"]

REC_NUMERIC_FEATURES: list[str] = ["age", "renta_log", "antiguedad", "ind_actividad_cliente"]
REC_CATEGORICAL_FEATURES: list[str] = ["segmento"]
REC_OWNED_FEATURES: list[str] = [f"possui_{i}" for i in QUESTIONNAIRE_ITEMS]

TEST_SIZE: float = 0.2
VALID_SIZE: float = 0.2          # fração do treino usada para early stopping
EVAL_K: list[int] = [1, 3, 7]    # 7 = métrica original da competição (MAP@7)
SHAP_SAMPLE: int = 2_000
LGBM_PARAMS: dict[str, object] = {
    "n_estimators": 500,
    "learning_rate": 0.05,
    "num_leaves": 31,
    "min_child_samples": 50,     # folhas com poucos clientes = overfitting em produtos raros
    "subsample": 0.8,
    "subsample_freq": 1,
    "colsample_bytree": 0.8,
    "reg_lambda": 1.0,
    "verbose": -1,
}
EARLY_STOPPING_ROUNDS: int = 50
# Item com menos clientes positivos que isso no treino não recebe modelo (D31):
# na base real, poupança tem ~4 positivos em 50 mil
MIN_POSITIVES_TO_TRAIN: int = 50

# ---------------------------------------------------------------------------
# Suitability e carteira (Etapa 6) — REGRAS DE NEGÓCIO, não features de modelo
# ---------------------------------------------------------------------------
# Opções válidas de cada pergunta e pontos atribuídos (inspirado na Res. CVM 30/2021:
# objetivos, horizonte, tolerância a risco e conhecimento/experiência).
SUITABILITY_POINTS: dict[str, dict[str, int]] = {
    "prazo": {"ate_1_ano": 0, "1_a_3_anos": 1, "3_a_5_anos": 2, "mais_de_5_anos": 3},
    "tolerancia": {  # "Se seus investimentos caíssem 20% em um mês, você..."
        "venderia_tudo": 0, "venderia_parte": 1, "manteria": 2, "compraria_mais": 3,
    },
    "objetivo": {
        "reserva": 0, "comprar_bem": 1, "renda_extra": 1, "aposentadoria": 2, "crescer_patrimonio": 3,
    },
    "experiencia": {"nenhuma": 0, "basica": 1, "intermediaria": 2, "avancada": 3},
    "idade": {"ate_34": 2, "35_a_54": 1, "55_ou_mais": 0},
}
# Pontuação total: 0–14. Faixas → perfil.
RISK_PROFILE_BANDS: list[tuple[int, int, str]] = [
    (0, 5, "conservador"),
    (6, 10, "moderado"),
    (11, 14, "arrojado"),
]
RISK_PROFILES: list[str] = ["conservador", "moderado", "arrojado"]
# Respostas que LIMITAM o perfil, independentemente da soma (a dimensão mais restritiva prevalece)
PROFILE_CAPS: dict[tuple[str, str], str] = {
    ("tolerancia", "venderia_tudo"): "conservador",
    ("prazo", "ate_1_ano"): "conservador",
    ("objetivo", "reserva"): "conservador",
    ("experiencia", "nenhuma"): "moderado",
}

# Saúde financeira (modo proteção): liquidez e reserva antes de qualquer risco
CARD_SPEND_LIMIT: float = 0.30       # gasto no cartão > 30% da renda = sinal de risco (regra prática)
EMERGENCY_RESERVE_MONTHS: int = 6    # reserva mínima = 6 meses de renda
PROTECTION_LIQUIDITY_MIN: int = 60   # % mínimo em liquidez no modo proteção

# Classes de ativo brasileiras usadas na carteira
BR_ASSET_CLASSES: dict[str, str] = {
    "liquidez": "Tesouro Selic / CDB liquidez diária",
    "renda_fixa": "Renda fixa pós-fixada / IPCA+ (CDB, LCI/LCA, Tesouro IPCA+)",
    "multimercado": "Fundos multimercado",
    "acoes": "Ações / ETFs",
    "previdencia": "Previdência privada (PGBL/VGBL)",
}
# Mapeamento explícito item do modelo (Santander) → classe brasileira (analogia, não equivalência)
ITEM_TO_BR_CLASS: dict[str, str] = {
    "poupanca": "liquidez",
    "deposito": "renda_fixa",
    "fundos": "multimercado",
    "acoes": "acoes",
    "previdencia": "previdencia",
}
# Faixas de alocação (% mínimo, % máximo) por perfil. O perfil define a faixa;
# as probabilidades do modelo definem onde, dentro da faixa, cada classe fica.
ALLOCATION_BANDS: dict[str, dict[str, tuple[int, int]]] = {
    "conservador": {"liquidez": (30, 60), "renda_fixa": (30, 60), "multimercado": (0, 10), "acoes": (0, 5), "previdencia": (0, 10)},
    "moderado": {"liquidez": (15, 30), "renda_fixa": (30, 50), "multimercado": (5, 20), "acoes": (5, 20), "previdencia": (0, 15)},
    "arrojado": {"liquidez": (5, 15), "renda_fixa": (15, 35), "multimercado": (10, 25), "acoes": (20, 45), "previdencia": (0, 20)},
}
MODEL_AFFINITY_FLOOR: float = 0.05   # afinidade mínima: classe com prob. ~0 ainda recebe parte do espaço livre

# ---------------------------------------------------------------------------
# Perguntas de refinamento (D33). Cada uma muda uma regra; nenhuma é só "informativa".
# ---------------------------------------------------------------------------
# Estabilidade da renda → tamanho da reserva-alvo (meses de renda)
INCOME_STABILITY_RESERVE_MONTHS: dict[str, int] = {
    "estavel": 6,        # CLT, servidor, aposentado
    "variavel": 12,      # autônomo, comissionado, empresário
    "sem_renda_fixa": 12,
}
# Dependentes → teto de perfil (mais pessoas dependendo da renda = menos capacidade de perda)
DEPENDENTS_OPTIONS: list[str] = ["nenhum", "1_a_2", "3_ou_mais"]
DEPENDENTS_CAP: dict[str, str] = {"3_ou_mais": "moderado"}
# Dívida cara (rotativo, cheque especial) → modo proteção, independentemente da reserva
EXPENSIVE_DEBT_OPTIONS: list[str] = ["nao", "sim"]
# Conhecimento declarado: a experiência efetiva é o MENOR entre o declarado e o inferido dos produtos
KNOWLEDGE_TO_EXPERIENCE: dict[str, str] = {
    "nenhum": "nenhuma", "basico": "basica", "intermediario": "intermediaria", "avancado": "avancada",
}
EXPERIENCE_ORDER: list[str] = ["nenhuma", "basica", "intermediaria", "avancada"]
# Chance de precisar do dinheiro antes do prazo → pontos percentuais extras no mínimo de liquidez
LIQUIDITY_NEED_BOOST: dict[str, int] = {"nao": 0, "talvez": 10, "sim": 20}

# ---------------------------------------------------------------------------
# Faixas do questionário (D34): o usuário escolhe uma faixa; o motor usa um valor
# representativo dela. Formato: chave → (rótulo, valor representativo).
# ---------------------------------------------------------------------------
INCOME_BANDS: dict[str, tuple[str, float]] = {     # renda mensal líquida, R$
    "ate_1500": ("Até R$ 1.500", 1_000.0),
    "1500_2500": ("R$ 1.500 a R$ 2.500", 2_000.0),
    "2500_4000": ("R$ 2.500 a R$ 4.000", 3_250.0),
    "4000_7000": ("R$ 4.000 a R$ 7.000", 5_500.0),
    "7000_12000": ("R$ 7.000 a R$ 12.000", 9_500.0),
    "acima_12000": ("Acima de R$ 12.000", 15_000.0),
}
CARD_SPEND_BANDS: dict[str, tuple[str, float]] = { # fração da renda gasta no cartão
    "nao_uso": ("Não uso cartão", 0.0),
    "ate_10": ("Até 10% da renda", 0.05),
    "10_30": ("De 10% a 30%", 0.20),
    "30_50": ("De 30% a 50%", 0.40),
    "acima_50": ("Mais de 50%", 0.60),
}
RESERVE_BANDS: dict[str, tuple[str, float]] = {    # meses de renda guardados
    "nao_tenho": ("Não tenho reserva", 0.0),
    "ate_3": ("Menos de 3 meses", 1.5),
    "3_6": ("De 3 a 6 meses", 4.5),
    "6_12": ("De 6 a 12 meses", 9.0),
    "acima_12": ("Mais de 12 meses", 15.0),
}
ACCOUNT_AGE_BANDS: dict[str, tuple[str, float]] = { # anos com conta em banco
    "menos_1": ("Menos de 1 ano", 0.5),
    "1_5": ("1 a 5 anos", 3.0),
    "5_10": ("5 a 10 anos", 7.5),
    "mais_10": ("Mais de 10 anos", 15.0),
}

# Informações em linguagem simples sobre cada classe (tela de resultado)
CLASS_INFO: dict[str, dict[str, object]] = {
    "liquidez": {
        "nome": "Liquidez diária",
        "o_que_e": "Aplicações que você resgata em até 1 dia útil, como Tesouro Selic e CDB de liquidez diária.",
        "papel": "Reserva de emergência e dinheiro para usar a qualquer momento.",
        "risco": 1, "resgate": "No mesmo dia ou no dia seguinte",
    },
    "renda_fixa": {
        "nome": "Renda fixa",
        "o_que_e": "Títulos que pagam juros combinados: CDB com prazo, LCI/LCA e Tesouro IPCA+.",
        "papel": "Base estável da carteira, com rendimento previsível e proteção contra a inflação.",
        "risco": 2, "resgate": "Em geral no vencimento (meses ou anos)",
    },
    "multimercado": {
        "nome": "Multimercado",
        "o_que_e": "Fundos que misturam juros, ações, câmbio e outros mercados, geridos por um profissional.",
        "papel": "Diversificação: busca ganhar acima da renda fixa com risco moderado.",
        "risco": 3, "resgate": "Alguns dias após o pedido",
    },
    "acoes": {
        "nome": "Ações / ETFs",
        "o_que_e": "Participação em empresas, direta ou por ETFs (fundos que copiam um índice como o Ibovespa).",
        "papel": "Crescimento no longo prazo, aceitando oscilações fortes no caminho.",
        "risco": 4, "resgate": "Em 2 dias úteis, mas o valor pode estar em queda",
    },
    "previdencia": {
        "nome": "Previdência",
        "o_que_e": "Planos PGBL/VGBL para a aposentadoria, com benefícios fiscais.",
        "papel": "Disciplina para o longo prazo e planejamento da aposentadoria.",
        "risco": 2, "resgate": "Possível, mas com custos e tributação maiores no curto prazo",
    },
}
RISK_LEVEL_LABELS: dict[int, str] = {1: "Muito baixo", 2: "Baixo", 3: "Médio", 4: "Alto"}
# Risco médio ponderado da carteira (1–4) → rótulo. Limites calibrados nas faixas de
# alocação: a carteira conservadora mais arriscada possível dá ~1,9 e a moderada ~2,45,
# então cada perfil cai no rótulo correspondente (evita "conservador" com risco "moderado").
PORTFOLIO_RISK_BANDS: list[tuple[float, str]] = [(2.0, "Baixo"), (2.5, "Moderado"), (4.01, "Alto")]
PROFILE_DESCRIPTIONS: dict[str, str] = {
    "conservador": "prioriza segurança e acesso ao dinheiro; aceita render menos para não ver o saldo cair.",
    "moderado": "busca equilíbrio: a maior parte em renda fixa e uma parcela em ativos que oscilam mais.",
    "arrojado": "aceita oscilações fortes no caminho em troca de mais potencial de crescimento no longo prazo.",
}

# Ponte de renda (D3/D16): renda mensal BRL → quintil brasileiro → renda espanhola do mesmo quintil.
# ATENÇÃO: limites APROXIMADOS de renda individual mensal; substituir pelos quintis oficiais da
# PNAD Contínua (IBGE) antes da apresentação.
BR_MONTHLY_INCOME_EDGES: list[float] = [1_500.0, 2_500.0, 4_000.0, 7_000.0]
# Segmento derivado por regra (o app não sabe o segmento bancário do usuário)
UNIVERSITY_AGE_MAX: int = 24
DEFAULT_ACTIVITY: int = 1            # quem usa o app é tratado como cliente ativo
N_RECOMMENDATIONS: int = 3
MIN_RECOMMEND_PROB: float = 0.10     # abaixo disso o item não é sugerido (sinal fraco demais)
MIN_ALLOCATION_PCT: int = 3          # classes opcionais com menos que isso são zeradas e redistribuídas
DISCLAIMER: str = (
    "Projeto acadêmico. Esta simulação NÃO é recomendação de investimento e não substitui "
    "a análise de um profissional certificado (CVM/ANBIMA). Modelos treinados com dados de "
    "clientes espanhóis (2015–2016)."
)

# ---------------------------------------------------------------------------
# Visualização — paleta validada para daltonismo (ordem fixa, nunca ciclar)
# ---------------------------------------------------------------------------
VIZ_SURFACE: str = "#fcfcfb"
VIZ_TEXT: str = "#0b0b0b"
VIZ_TEXT_MUTED: str = "#52514e"
VIZ_GRID: str = "#e4e3df"
VIZ_NEUTRAL_MID: str = "#f0efec"  # ponto médio de escalas divergentes
# Uma cor fixa por classe de produto (a cor segue a classe em todos os gráficos)
VIZ_GROUP_COLORS: dict[str, str] = {
    "liquidez": "#2a78d6",
    "renda_fixa": "#eb6834",
    "renda_variavel": "#1baf7a",
    "longo_prazo": "#eda100",
    "credito": "#e87ba4",
}
# Paleta categórica para clusters: ordem fixa validada (nunca ciclar)
VIZ_CATEGORICAL: list[str] = [
    "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948",
]
VIZ_BACKGROUND_POINTS: str = "#d6d5d0"
VIZ_SEQUENTIAL: list[str] = [  # azul, claro → escuro (magnitude)
    "#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b",
]
VIZ_DIVERGING: tuple[str, str] = ("#2a78d6", "#e34948")  # negativo, positivo
VIZ_DPI: int = 150

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_LEVEL: str = "INFO"
LOG_FORMAT: str = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
