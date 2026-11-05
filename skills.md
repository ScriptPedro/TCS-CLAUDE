---
name: assessor-investimentos
description: Guia técnico do Assessor de Investimentos Virtual (projeto final de IA Aplicada / BFSI). Use para entender, executar, manter ou defender o projeto. Cobre comandos, arquitetura, regras de negócio de suitability, modelos de ML (K-Means, GMM, LightGBM, SHAP) e por que foram escolhidos, contratos da API, testes, limitações e convenções de código.
---

# Skills — Assessor de Investimentos Virtual

> Documento de referência técnica, escrito para quem vai **rodar, manter, evoluir ou defender** o projeto.
> Ele resume o que está espalhado em `README.md`, `docs/decisoes.md` (D1–D38), `docs/limitacoes.md`,
> `reports/*.md` e no código. Quando houver divergência, **o código e o `src/config.py` são a fonte da verdade**.

> ⚠️ Projeto acadêmico. **Não é recomendação de investimento.** Os modelos foram treinados com dados de
> clientes espanhóis do Santander (2015–2016).

---

## Sumário

1. [Visão geral em 30 segundos](#1-visão-geral-em-30-segundos)
2. [Stack e versões](#2-stack-e-versões)
3. [Comandos principais](#3-comandos-principais)
4. [Arquitetura](#4-arquitetura)
5. [Pipeline de dados](#5-pipeline-de-dados)
6. [Modelos de Machine Learning e por que foram escolhidos](#6-modelos-de-machine-learning-e-por-que-foram-escolhidos)
7. [Regras de negócio (motor de suitability)](#7-regras-de-negócio-motor-de-suitability)
8. [Ponte questionário → modelo](#8-ponte-questionário--modelo)
9. [API HTTP (FastAPI)](#9-api-http-fastapi)
10. [Front-ends](#10-front-ends)
11. [Qualidade: testes, personas e auditoria de viés](#11-qualidade-testes-personas-e-auditoria-de-viés)
12. [Resultados com os dados reais](#12-resultados-com-os-dados-reais)
13. [Ética, LGPD e regulação](#13-ética-lgpd-e-regulação)
14. [Limitações conhecidas](#14-limitações-conhecidas)
15. [Convenções de código e como evoluir](#15-convenções-de-código-e-como-evoluir)
16. [Solução de problemas](#16-solução-de-problemas)
17. [Próximos passos](#17-próximos-passos)
18. [Mapa de arquivos](#18-mapa-de-arquivos)

---

## 1. Visão geral em 30 segundos

O usuário responde a um questionário de 14 perguntas em 4 etapas e recebe:

| # | Saída | Quem decide |
|---|---|---|
| 1 | **Segmento de cliente** em que se encaixa | IA: K-Means (`src/segmentation.py`) |
| 2 | **Produtos** mais comuns entre clientes parecidos, com probabilidade e motivo | IA: LightGBM + SHAP (`src/recommender.py`) |
| 3 | **Perfil de risco** e **carteira sugerida** por classe de ativo brasileira | Regras de negócio (`src/portfolio.py`) + afinidade do modelo |
| 4 | **Explicação** em linguagem simples, alertas e próximos passos | Template determinístico (`src/portfolio.py`) |

**Princípio central do projeto:**

> **O perfil define a FAIXA; o modelo define a POSIÇÃO dentro dela.**
>
> O modelo aprende *o que clientes parecidos têm*, não *o que é adequado ter*. A adequação vem de regras
> explícitas e auditáveis. O ML só ajusta pesos dentro dos limites que as regras permitem.

---

## 2. Stack e versões

| Camada | Tecnologia | Observação |
|---|---|---|
| Linguagem | **Python 3.12** (`requires-python >=3.11,<3.13`; 3.13 não instala numpy 1.26 / numba 0.60) | Versões fixadas em `requirements.txt` |
| Dados | pandas 2.2.3, numpy 1.26.4, pyarrow 17 | Parquet como formato intermediário |
| ML | scikit-learn 1.5.2, LightGBM 4.5.0, SHAP 0.46.0 | `numba==0.60.0` e `contourpy==1.3.0` fixados (D21) |
| Visualização | matplotlib, seaborn, plotly | Paleta validada para daltonismo no `config.py` |
| App 1 | Streamlit 1.39 | `app/main.py` |
| API | FastAPI 0.115 + Uvicorn 0.32 | `api/main.py` |
| App 2 | React 18.3 + Vite 5.4 + TypeScript 5.6 | `frontend/`, Node 18+ |
| Testes | pytest 8.3, httpx (TestClient), `streamlit.testing.AppTest` | `tests/` |
| Dados externos | Kaggle API 1.6 | Competição *santander-product-recommendation* |

**Por que versões fixas:** `numba` e `contourpy` recentes puxam numpy 2.x, que quebra o import do `shap 0.46`.
Não atualize uma dessas libs isoladamente.

---

## 3. Comandos principais

Todos os comandos rodam **na raiz do projeto**.

### 3.1 Ambiente

```powershell
# Windows / PowerShell (use um caminho curto, ex.: C:\projetos\assessor — limite de 260 caracteres)
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

```bash
# Linux / macOS
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3.2 Dados (Kaggle)

1. Aceite as regras da competição em
   <https://www.kaggle.com/competitions/santander-product-recommendation/rules>. Sem esse passo a API retorna **403**.
2. Gere o token em *Settings → API → Create New Token* e salve o `kaggle.json` em `~/.kaggle/`
   (Windows: `C:\Users\<usuario>\.kaggle\`).
3. Baixe:

```bash
python -m src.download_data
```

O arquivo vai para `data/raw/train_ver2.csv` (~2,3 GB, ~13,6 M linhas). **Não versionar** (regras da competição).

### 3.3 Pipeline

| Objetivo | Comando | Saída principal |
|---|---|---|
| **Tudo de uma vez** | `python -m src.pipeline` | Todos os artefatos abaixo |
| Ensaio isolado (não toca em `data/`, `models/`, `reports/`) | `python -m src.pipeline --out ensaio --sample-size 5000` | Pasta `ensaio/` |
| Outro CSV de entrada | `python -m src.pipeline --input outro.csv` | — |
| Etapa 2: preparação | `python -m src.prepare_data` | `data/processed/santander_50k.parquet`, `models/prep_stats.json`, `reports/qualidade_dados.md` |
| Etapa 3: EDA | `jupyter lab notebooks/01_eda.ipynb` | Figuras 01–10 |
| Etapa 4: segmentação | `python -m src.segmentation` (forçar k: `--k 5`) | `models/segmentation.joblib`, `santander_50k_clusters.parquet`, figuras 11–14 |
| Etapa 5: recomendação | `python -m src.recommender` | `models/recommender.joblib`, figuras 15–18 |
| Etapa 8: personas | `python -m src.personas` | `reports/personas.md` |
| Etapa 8: auditoria de viés | `python -m src.bias_audit` | `reports/auditoria_vies.md` |

**Ordem obrigatória:** `prepare_data` → `segmentation` → `recommender`. O app precisa dos três artefatos:
`segmentation.joblib`, `recommender.joblib` e `prep_stats.json`.

O `pipeline` termina com `SystemExit` se alguma persona falhar, então ele funciona como teste de aceitação.

### 3.4 Aplicações

```bash
# Streamlit → http://localhost:8501
streamlit run app/main.py

# API FastAPI → http://localhost:8000 (docs em /docs)
uvicorn api.main:app --reload --port 8000

# Front React em modo dev → http://localhost:5173 (proxy de /api para :8000)
cd frontend && npm install && npm run dev

# Apresentação com um só servidor: compila o front e a API passa a servi-lo em :8000
cd frontend && npm run build
uvicorn api.main:app --port 8000
```

Variável de ambiente útil:

| Variável | Uso |
|---|---|
| `ASSESSOR_MODELS_DIR` | Pasta alternativa com os 3 artefatos (Streamlit e API) |

### 3.5 Testes

```bash
pytest                        # tudo (config em pyproject.toml: -q, sem cache)
pytest tests/test_portfolio.py -k protecao   # um subconjunto
```

Os testes usam **dados sintéticos** (`tests/fakes.py`) e não precisam do CSV do Kaggle.

---

## 4. Arquitetura

### 4.1 Visão em camadas

```
┌──────────────────────── Apresentação ────────────────────────┐
│ app/main.py (Streamlit)     frontend/ (React + Vite + TS)    │
│        │                           │ HTTP JSON                │
│        │                    api/main.py (FastAPI)             │
│        └──────────┬────────────────┘                          │
│          app/components.py  ← perguntas, validação, avisos    │
│                   │            (sem Streamlit; testável)      │
└───────────────────┼──────────────────────────────────────────┘
                    ▼
┌──────────── Orquestração: src/advisor.py (única ponte) ──────┐
│ questionario_para_linha() → features no formato do dataset   │
│ aconselhar() → cluster + P(item) + carteira + texto           │
└──────┬──────────────────────────────────────┬────────────────┘
       ▼                                      ▼
┌──── IA (aprendida dos dados) ────┐  ┌── Regras de negócio (SEM ML) ──┐
│ segmentation.py  K-Means → seg.  │  │ portfolio.py                    │
│ recommender.py   LightGBM → P()  │  │  calcular_perfil() suitability  │
│                  SHAP → por quê  │  │  avaliar_saude()   proteção     │
└──────────────────────────────────┘  │  faixas_efetivas() (mín, máx)   │
                                      │  alocar()  water-filling        │
                                      │  gerar_explicacao() template    │
                                      └─────────────────────────────────┘
┌─────────── Treino offline (src/pipeline.py) ──────────────────┐
│ download_data → prepare_data → segmentation → recommender     │
│               → personas → bias_audit                          │
└───────────────────────────────────────────────────────────────┘
               src/config.py: TODAS as constantes e premissas
```

### 4.2 Princípios de arquitetura (e onde estão garantidos)

| Princípio | Como é garantido | Decisão |
|---|---|---|
| **Regra de negócio ≠ feature** | Perguntas sem correspondência no dataset (cartão, reserva, objetivo, prazo, tolerância) só alimentam regras | D4 |
| **Separação física regras × ML** | `src/portfolio.py` não importa nenhum modelo; dá para testar regras sem treinar nada | D22 |
| **Ponte única** | `src/advisor.py` é o único módulo que conhece questionário, modelos e regras | D16, D22 |
| **App fino** | `app/main.py` só faz layout; lógica em `app/components.py` (sem Streamlit) e `src/` | D28 |
| **Sem duplicação no front** | A API reaproveita `app/components.py` e `src/advisor.py`; o React só renderiza | README |
| **Config central** | Nenhum número mágico fora de `src/config.py` | — |
| **Regra prevalece sobre probabilidade** | `recomendar_produtos()` filtra itens de classes zeradas pelo perfil | D24 |
| **Determinismo** | `RANDOM_STATE = 42`; explicação por template, não por LLM | D26 |

### 4.3 Fluxo de uma requisição

```
POST /api/recomendacao {respostas}
 └─ components.montar_questionario()  faixas → valores representativos → Questionario (valida)
     └─ advisor.aconselhar(q, artefatos)
         ├─ questionario_para_linha()   renda BRL→quintil→EUR, segmento por regra, produtos→24 colunas
         ├─ segmentation.assign_cluster()          → cluster_id, nome, descrição
         ├─ recommender.predict_proba()             → P(item) para 5 itens
         ├─ portfolio.montar_carteira(q, probs)     → perfil, saúde, faixas, alocação (soma 100)
         ├─ recomendar_produtos()                   → top-3 itens permitidos com P ≥ 10% + SHAP
         └─ portfolio.gerar_explicacao()            → texto
 └─ api.serializar()  → JSON para a tela de resultado
```

---

## 5. Pipeline de dados

### 5.1 Fonte

Kaggle *Santander Product Recommendation*, `train_ver2.csv`: 17 meses (jan/2015–mai/2016), ~950 mil clientes,
24 produtos binários (`ind_*_ult1`) e dados demográficos.

### 5.2 Preparação (`src/prepare_data.py`)

| Passo | Regra | Por quê |
|---|---|---|
| Leitura | `read_csv(chunksize=500_000, usecols=USECOLS)`, filtrando cada chunk | Pico de memória em centenas de MB em vez de ~8 GB (D2) |
| Snapshot | Só `fecha_dato == 2016-05-28` → 1 linha por cliente | Evita o mesmo cliente várias vezes e vazamento treino/teste (D1) |
| Ordem | **Filtrar → amostrar → imputar** | Garante exatamente 50 mil válidos; estatísticas coerentes com `prep_stats.json` (D7) |
| Idade | Mantém 18 ≤ idade ≤ 100 | 8.362 removidos |
| Amostra | **50.000 clientes**, estratificada por `segmento`, `random_state=42` | Proporções idênticas à população |
| Renda | Winsorização **p1–p99** → imputação pela mediana de **segmento × faixa etária** (fallback: global) + flag `renta_imputada` | Caudas de dezenas de milhões de euros; ~25% nulos (D8) |
| Antiguidade | Negativo (`-999999`) = desconhecido → mediana da faixa etária + flag `antiguedad_imputada` | São códigos, não meses (D9) |
| Categóricas | Nulo → `"desconhecido"` | Não descarta clientes (D10) |
| Produtos | Nulo → 0 | Ausência = não possui (D10) |
| Renda relativa | Quintis (`muito_baixa` … `muito_alta`) | Euro de 2016 ≠ real de hoje (D3) |
| Persistência | Parquet + `models/prep_stats.json` (medianas, limites, quintis) | O app trata a entrada do usuário do mesmo jeito que o treino |

Funil real: 13.647.309 linhas → 931.453 no snapshot → 50.000 na amostra (38 colunas).

### 5.3 Engenharia de features (`src/features.py`)

| Feature | Definição | Usada em |
|---|---|---|
| `n_<classe>` | Contagem de produtos por classe (liquidez, renda fixa, renda variável, longo prazo, crédito) | Segmentação |
| `n_produtos`, `possui_investimento` | Totais agregados | EDA |
| `renta_log` | `log(renta)` — cauda longa, distância relativa | Segmentação e recomendação |
| `possui_<item>` | 8 itens do questionário (conta, poupança, depósito, fundos, ações, previdência, cartão, empréstimo) | Recomendação |

Os 24 produtos são agrupados porque são esparsos (vários com < 1% de posse) e alguns são quase duplicados (D13).

---

## 6. Modelos de Machine Learning e por que foram escolhidos

### 6.1 Resumo

| Problema | Modelo escolhido | Alternativa comparada | Descartado |
|---|---|---|---|
| Segmentar clientes | **K-Means (k = 4)** | GMM (Gaussian Mixture) | Autoencoder + K-Means |
| Prever afinidade por produto | **LightGBM, 1 classificador binário por item** | Popularidade no cluster e popularidade global (baselines) | Multi-label único, MLP |
| Explicar a previsão | **SHAP (TreeExplainer)** | — | — |
| Gerar o texto | **Template determinístico** | — | LLM (fica como próximo passo) |

### 6.2 Segmentação — K-Means

**Features (sem `sexo`, D11):**
- Contínuas com `StandardScaler`: `age`, `renta_log`, `antiguedad`
- Binárias e contagens com `MinMaxScaler` 0–1: `ind_actividad_cliente`, `n_liquidez`, `n_renda_fixa`,
  `n_renda_variavel`, `n_longo_prazo`, `n_credito`
- Categórica com one-hot: `segmento`

**Por que K-Means:**
- Centróides interpretáveis: cada cluster tem um "cliente típico" que dá para nomear e explicar à banca.
- Rápido em 50 mil linhas; atribuir um novo usuário é calcular a distância a 4 centróides.
- Com a escala por tipo, os resultados foram estáveis (ARI de bootstrap 0,992).

**Por que não o GMM como principal:** foi comparado com as mesmas métricas e perdeu nos dados reais
(silhouette 0,205 contra 0,301; Davies-Bouldin 2,85 contra 1,37; menor cluster com 5,2% da base). O GMM
permite clusters elípticos e atribuição probabilística, mas aqui não compensou. ARI entre os dois: 0,51.

**Por que não autoencoder:** exigiria PyTorch/TensorFlow para reduzir ~13 features. Ganho pequeno e
perda de explicabilidade (D12).

**Escala por tipo (D14) — problema real resolvido:** com `StandardScaler` em tudo, uma binária rara
(previdência) ficava a muitos desvios-padrão da média e o K-Means criava um cluster só para ela. Na base
sintética com 4 personas plantadas, a escala por tipo levou o ARI de 0,89 para 0,997.

**Escolha de k (D15):** avalia k = 2..10 (inércia, silhouette numa amostra de 10 mil, Davies-Bouldin,
Calinski-Harabasz, BIC do GMM). Regra: **maior silhouette dentro da faixa de negócio [4, 8]**. Abaixo de 4 os
segmentos ficam genéricos demais para recomendar; acima de 8 ficam difíceis de nomear. O cotovelo (k = 5) e
o BIC entram como evidência complementar. Resultado: **k = 4**.

**Clusters reais:**

| ID | Nome | % da base | Idade média | % investe | Segmento predominante |
|---|---|---|---|---|---|
| 0 | Jovem só conta | 36,9% | 24 | 0,3% | universitário |
| 1 | Maduro investidor | 25,4% | 56 | 13,1% | particulares |
| 2 | Adulto só conta | 24,5% | 43 | 5,8% | particulares |
| 3 | Maduro investidor (B) | 13,2% | 52 | 15,1% | particulares (renda mediana 2,3× maior) |

Nomes gerados por regra; revisão humana via `CLUSTER_NAME_OVERRIDES` no `config.py`.

### 6.3 Recomendação — LightGBM (um modelo por item)

**Formulação (D17):**
- **Alvos:** os 5 itens de investimento do questionário: poupança, CDB/depósito, fundos, ações, previdência.
  Crédito nunca é alvo (D5).
- **Features:** `age`, `renta_log`, `antiguedad`, `ind_actividad_cliente`, `segmento` + os **outros** itens
  possuídos (`possui_*`). O modelo de "fundos" **não vê** `possui_fundos`, o que seria vazamento do alvo.
- **Granularidade do questionário, não os 24 produtos:** o modelo só aprende o que o app consegue perguntar.

**Por que LightGBM:**
- Estado da arte para dados **tabulares** de tamanho médio; lida com relações não lineares e interações
  (idade × renda × co-posse) sem engenharia manual.
- Rápido de treinar (menos de 1 minuto com SHAP).
- Compatível com `SHAP TreeExplainer` (explicação exata e rápida por cliente).
- MLP foi descartado: menos interpretável e não supera boosting nesse tipo de dado.
- Um modelo por item (em vez de multi-label único): permite remover o próprio item das features de forma
  simples e treinar/pular itens de forma independente.

**Hiperparâmetros (`LGBM_PARAMS`):**

```python
n_estimators=500, learning_rate=0.05, num_leaves=31,
min_child_samples=50,          # folhas com poucos clientes = overfitting em produtos raros
subsample=0.8, subsample_freq=1, colsample_bytree=0.8, reg_lambda=1.0
early_stopping_rounds=50       # monitorando binary_logloss
```

**Early stopping pela log loss, não pela AUC (D19) — problema real resolvido:** monitorando a AUC, o treino
parava com 5 a 13 árvores e as probabilidades ficavam presas na taxa média (posse real de 71% prevista em 34%).
Para ranquear itens **diferentes** para o mesmo cliente, as probabilidades precisam estar calibradas entre
itens. Com `binary_logloss` + `first_metric_only=True`: 57 a 86 árvores e precision@1 de 0,53 para 0,59
(na base sintética).

**Itens raríssimos (D31):** poupança tem ~4 positivos em 50 mil. Itens com menos de
`MIN_POSITIVES_TO_TRAIN = 50` positivos não recebem modelo: a probabilidade é a taxa média e não há SHAP.
A validação interna é estratificada pelo alvo.

**Divisão:** 80/20 treino/teste (`TEST_SIZE`) e mais 20% do treino para early stopping (`VALID_SIZE`).

### 6.4 Avaliação honesta (D18, D20)

A competição original mede MAP@7 de produtos **novos** entre meses. Com um único snapshot isso não é
possível, então são usadas três visões e **dois baselines obrigatórios**:

1. **AUC por item:** separa quem tem de quem não tem.
2. **precision@k / MAP@k:** ranqueando os 5 itens. Com 5 itens, MAP@7 = MAP@5, e isso é dito explicitamente.
3. **Leave-one-out (Hit@k, MRR):** esconde um item possuído e mede se ele volta ao topo entre os não possuídos.
   É o análogo mais próximo do uso real do app.

| Modelo | AUC média | precision@1 | LOO Hit@1 | LOO MRR |
|---|---|---|---|---|
| **LightGBM** | **0,846** | **0,527** | **0,551** | **0,736** |
| Popular no cluster | 0,780 | 0,512 | 0,475 | 0,696 |
| Popular global | 0,500 | 0,512 | 0,475 | 0,696 |

AUC por item do LightGBM: CDB 0,945 · fundos 0,932 · ações 0,918 · previdência 0,934.

**Como defender:** o LightGBM vence onde importa (AUC, Hit@1 e MRR do leave-one-out). Em MAP@3/MAP@7 o baseline
de popularidade empata ou fica levemente à frente, porque com 5 itens e posse muito concentrada o ranking
"mais popular primeiro" já é forte. Nos testes sintéticos (D20), o LightGBM só vence quando há sinal
**individual** além do segmento, e os dados reais mostram que esse sinal existe.

### 6.5 Explicabilidade — SHAP

- `TreeExplainer` em amostra de 2.000 clientes (`SHAP_SAMPLE`) para o relatório global (heatmap, beeswarm).
- Por usuário: `recommender.explain()` devolve os 3 fatores de maior |SHAP| com a direção (↑/↓).
- Fator mais importante nos dados reais: **cliente ativo**, seguido de antiguidade e idade.
- **Bug corrigido (D26):** o texto dizia "Já tem CDB" para quem **não** tinha. O rótulo agora depende do
  valor da feature ("Já tem…" ou "Ainda não tem…").

---

## 7. Regras de negócio (motor de suitability)

Tudo em `src/portfolio.py`, parametrizado em `src/config.py`. **Nenhum ML aqui.**

### 7.1 Pontuação de perfil (inspirada na Res. CVM 30/2021 — D23)

| Dimensão | Respostas → pontos |
|---|---|
| Prazo | até 1 ano **0** · 1–3 anos **1** · 3–5 anos **2** · > 5 anos **3** |
| Reação a queda de 20% | venderia tudo **0** · venderia parte **1** · manteria **2** · compraria mais **3** |
| Objetivo | reserva **0** · comprar bem / renda extra **1** · aposentadoria **2** · crescer patrimônio **3** |
| Experiência | nenhuma **0** · básica **1** · intermediária **2** · avançada **3** |
| Idade | até 34 **2** · 35–54 **1** · 55+ **0** |

Total de 0 a 14 → **0–5 conservador · 6–10 moderado · 11–14 arrojado**.

**Experiência efetiva** = o **menor** nível entre:
- o inferido dos produtos: ações → avançada; fundos/previdência → intermediária; poupança/CDB → básica; nada → nenhuma;
- o conhecimento declarado (D33).

### 7.2 Tetos de perfil (a resposta mais restritiva prevalece)

| Condição | Perfil máximo |
|---|---|
| "Venderia tudo" numa queda de 20% | conservador |
| Prazo de até 1 ano | conservador |
| Objetivo = reserva de emergência | conservador |
| Nenhuma experiência | moderado |
| 3 ou mais dependentes | moderado |

Sem tetos, a soma de pontos produziria "um arrojado que vende tudo na primeira queda".

### 7.3 Saúde financeira e modo proteção (D24, D33)

O **modo proteção** é ativado se qualquer um for verdadeiro:

| Gatilho | Regra |
|---|---|
| Cartão alto | gasto no cartão **> 30%** da renda |
| Sem reserva | reserva **< 6 meses** de renda (**12 meses** se a renda for variável ou não fixa) |
| Dívida cara | paga juros de rotativo ou cheque especial |

**Efeito:** perfil efetivo = conservador; liquidez **≥ 60%**; multimercado, ações e previdência **zerados**;
o modelo fica proibido de sugerir produtos dessas classes. Ter empréstimo gera alerta, mas não ativa proteção.

A reserva é medida em meses de **renda** (o questionário não pergunta custo de vida), o que é conservador.

### 7.4 Faixas de alocação por perfil (% mín, % máx)

| Classe brasileira | Conservador | Moderado | Arrojado |
|---|---|---|---|
| Liquidez (Tesouro Selic / CDB liquidez diária) | 30–60 | 15–30 | 5–15 |
| Renda fixa (CDB, LCI/LCA, Tesouro IPCA+) | 30–60 | 30–50 | 15–35 |
| Multimercado | 0–10 | 5–20 | 10–25 |
| Ações / ETFs | 0–5 | 5–20 | 20–45 |
| Previdência (PGBL/VGBL) | 0–10 | 0–15 | 0–20 |

**Necessidade de liquidez antes do prazo:** talvez **+10** p.p., sim **+20** p.p. no mínimo de liquidez.
Se a soma dos mínimos passar de 100%, a renda fixa cede primeiro, depois as demais.

`validar_faixas()` garante Σmín ≤ 100 ≤ Σmáx; o pior caso (proteção + 20 p.p.) é testado.

### 7.5 Algoritmo de alocação (`alocar`, D25)

1. Cada classe começa no **mínimo** da faixa.
2. O espaço livre é repartido **proporcionalmente à afinidade do modelo**, com piso de 0,05
   (`MODEL_AFFINITY_FLOOR`), sem ultrapassar o máximo. O excedente de quem atinge o teto é redistribuído
   (**water-filling**).
3. Arredondamento pelo **maior resto**: inteiros que sempre somam 100.
4. `alocar_sem_residuos`: classes opcionais com menos de **3%** são zeradas e a alocação é refeita.

**Afinidade por classe** = P(item) mapeado pela analogia Santander → Brasil:

| Item do modelo | Classe brasileira |
|---|---|
| poupança | liquidez |
| depósito a prazo | renda fixa |
| fundos | multimercado |
| valores mobiliários / derivativos | ações / ETFs |
| plano de pensões | previdência |

**Garantia testada:** para afinidades aleatórias × 3 perfis, a soma é 100 e toda classe fica dentro da faixa.

### 7.6 Produtos sugeridos

- Só itens que o usuário **não tem**, de classes **permitidas** pela carteira, com **P ≥ 10%**, no máximo **3**.
- Cada item vem com os 3 fatores SHAP traduzidos para linguagem simples.

### 7.7 Risco da carteira e texto (D26, D35)

- Risco por classe: liquidez 1, renda fixa 2, multimercado 3, ações 4, previdência 2.
- Nota = média ponderada (1–4). Rótulos: **< 2,0 Baixo · < 2,5 Moderado · senão Alto**. Os limites foram
  calibrados para o rótulo **nunca ficar acima do perfil** (teste com 300 carteiras aleatórias por perfil).
- Texto por **template** (mesma entrada → mesmo texto; sem risco de alucinação): "Em resumo" em 3 frases,
  um cartão por classe ("R$ X de cada R$ 1.000", o que é, para que serve, risco, prazo de resgate e por que essa %),
  e próximos passos ordenados (quitar dívida → completar reserva → investir → rebalancear).
- Linguagem: "clientes com perfil parecido **têm**", nunca "você **deve** ter" (correlação ≠ causalidade).

---

## 8. Ponte questionário → modelo

O usuário do app não é cliente Santander. `advisor.questionario_para_linha()` monta uma linha no formato do
dataset (D16, D27, D34):

| Feature do modelo | Origem no app |
|---|---|
| `age` | Idade digitada (18–100) |
| `renta` | Faixa de renda BRL → valor representativo → **quintil brasileiro** (limites oficiais da PNAD Contínua 2025: R$ 1.504 / 1.829 / 2.546 / 4.470) → média geométrica dos limites do mesmo quintil na base espanhola |
| `antiguedad` | Faixa "tempo de conta em banco" × 12 meses (limitado a idade − 16 anos) |
| `ind_actividad_cliente` | Fixo em 1 (quem usa o app é ativo) |
| `segmento` | Regra: idade ≤ 24 → universitário; renda acima do P95 (R$ 10.174) → top; senão particulares (D37) |
| 24 produtos | Pergunta "Quais destes produtos você já tem?": cada item ativa o 1º produto do grupo |

### Questionário (4 etapas, 14 perguntas)

| Etapa | Perguntas | Alimenta |
|---|---|---|
| Sobre você | idade · dependentes · estabilidade da renda · faixa de renda | modelo + tetos + reserva-alvo |
| Suas finanças | % da renda no cartão · dívida cara · meses de reserva · tempo de conta | modo proteção + modelo |
| Seus objetivos | objetivo · prazo · necessidade de liquidez | pontuação + faixas |
| Você e o risco | reação a queda de 20% · conhecimento · produtos que já tem | pontuação + modelo |

**Regras do formulário:**
- Valores são escolhidos por **faixas**, e cada faixa vira um valor representativo
  (ex.: "R$ 4.500 a R$ 10.000" → R$ 7.000).
- **As bordas das faixas coincidem com os limites das regras** (30% no cartão; 6 e 12 meses de reserva):
  a faixa escolhida decide a regra sem ambiguidade. Há teste para isso.
- **Minimização (LGPD):** nenhuma pergunta é só informativa; cada uma muda uma regra ou uma feature.
- `montar_questionario()` nunca lança exceção para o usuário: devolve mensagens amigáveis.
- `avisos_de_consistencia()` aponta combinações suspeitas, mas possíveis, e segue em frente.

---

## 9. API HTTP (FastAPI)

Arquivo: `api/main.py`. Documentação interativa em `http://localhost:8000/docs`.

| Método | Rota | Resposta |
|---|---|---|
| `GET` | `/api/saude` | `{"modelos": bool, "erro": str \| null}` |
| `GET` | `/api/questionario` | Etapas, perguntas (`campo`, `texto`, `tipo`, `opcoes`, `padrao`, `ajuda`), respostas padrão e aviso legal |
| `POST` | `/api/recomendacao` | Corpo `{"respostas": {...}}` → resultado completo |
| `GET` | `/{caminho}` | Front compilado (`frontend/dist`), só se existir; bloqueia `../` fora da pasta |

**Códigos de erro:**
- `422` — respostas inválidas: `{"detail": {"erros": [...]}}`
- `503` — modelos não encontrados (rode o pipeline)

**Resposta de `/api/recomendacao` (campos principais):** `avisos`, `resumo`, `perfil` (efetivo, pela soma,
pontos, limitado_por, detalhamento), `risco` (nota, rótulo), `segmento` (id, nome, descrição),
`saude` (modo_protecao, alertas), `carteira` (por classe: pct, por_mil, faixa mín/máx, afinidade, motivo…),
`proximos_passos`, `produtos` (rótulo, classe, prob, fatores), `texto`, `aviso`.

Os artefatos são carregados uma vez por pasta (`lru_cache`).

---

## 10. Front-ends

### Streamlit (`app/main.py`)
- Assistente em 4 etapas com barra de progresso, "Voltar" preservando respostas e "Ajustar respostas".
- **Sem `st.rerun()` (D29):** o formulário fica num `st.empty()` e o resultado é desenhado na mesma execução;
  "Refazer" usa `on_click`. Evita execução dupla e widgets "fantasma" no `AppTest`.
- **Escape de `$` (D35):** todo texto dinâmico passa por `md()`, porque o Streamlit interpreta `$…$` como LaTeX.
- Números no padrão brasileiro via `fmt_brl` / `fmt_num` (`src/utils.py`).
- Tema em `.streamlit/config.toml` (rode na raiz). Ao alterar `src/`, **reinicie** o servidor.

### React (`frontend/`)
- React 18 + Vite + TypeScript. Componentes: `Inicio`, `Questionario`, `Resultado`, `Rosca` (gráfico de rosca).
- `src/api.ts` encapsula as chamadas e converte erros em `ErroApi`.
- Em dev, o Vite faz proxy de `/api` para `:8000`. Em produção, a API serve o `dist/`.
- **Nenhuma regra no front**: tudo vem pronto da API.

**Gráfico de rosca (D30):** no máximo 5 fatias, cor fixa por classe (paleta validada para daltonismo),
classes com 0% omitidas. Layout verificado em 375 px e 640 px.

---

## 11. Qualidade: testes, personas e auditoria de viés

### 11.1 Testes automatizados (`tests/`, 93 funções de teste, 248 casos com a parametrização)

| Arquivo | Cobre |
|---|---|
| `test_prepare_data.py` | Leitura em chunks, limpeza, imputação, estratificação |
| `test_features_eda.py` | Contagens por classe, flags, insights |
| `test_segmentation.py` | Escolha de k, escala por tipo, atribuição de cluster |
| `test_recommender.py` | Sem vazamento do alvo, métricas, item raro sem modelo, SHAP |
| `test_portfolio.py` | Pontuação, tetos, modo proteção, faixas viáveis, alocação soma 100 e dentro da faixa, rótulo de risco |
| `test_app.py` | Fluxo Streamlit completo com `AppTest` (envio, proteção, inválidos, refazer, sem modelos) |
| `test_api.py` | Rotas FastAPI, 422/503, serialização |
| `test_pipeline.py` | Pipeline ponta a ponta com dados sintéticos |
| `fakes.py` | Gerador de CSV sintético que imita o formato e as "sujeiras" do arquivo real |

### 11.2 Personas (`src/personas.py`) — teste de aceitação

| Persona | Esperado | Resultado real |
|---|---|---|
| Jovem endividado | conservador, 5 pts, proteção, liquidez ≥ 60%, 0% em risco | ✅ Liquidez 65% · RF 35% |
| Adulto moderado | moderado, 8 pts, sem proteção, ações 5–20% | ✅ Ações 20% |
| Investidor experiente | arrojado, 13 pts, ações 20–45%, ações > liquidez | ✅ Ações 37% |

### 11.3 Auditoria de viés (`src/bias_audit.py`)

- `sexo` **não é feature** e **não é perguntado**; só é usado aqui (D11).
- **Regra dos 4/5:** razão de impacto = menor média ÷ maior média; abaixo de 0,8 → alerta.
- **V de Cramér** cluster × sexo = 0,169 (contra 0,550 para cluster × faixa etária).
- Resultado: 4 alertas gerais (razões 0,63–0,74). **Controlando pela idade**, a maioria volta a ≥ 0,8: a
  disparidade é majoritariamente **idade como proxy** (grupo H é ~4 anos mais jovem). Restam 3 casos residuais
  (fundos em 25–34 e 55–64; ações em 55–64), apresentados como limitação (D32).
- **Mitigação:** a recomendação final passa pelo motor de suitability, que usa só respostas do próprio usuário.

---

## 12. Resultados com os dados reais

| Métrica | Valor |
|---|---|
| Clientes na amostra | 50.000 (38 colunas) |
| k escolhido | 4 (silhouette 0,301; estabilidade ARI 0,992) |
| AUC média LightGBM × cluster × global | 0,846 × 0,780 × 0,500 |
| LOO Hit@1 LightGBM × baseline | 0,551 × 0,475 |
| Itens sem modelo | Poupança (< 50 positivos) |
| Personas | 3/3 aprovadas |
| Alertas de viés (sexo) | 4 gerais, 3 residuais após controle por idade |

---

## 13. Ética, LGPD e regulação

- **Minimização:** sem nome, CPF, contato ou sexo. Toda pergunta muda uma regra.
- **Sem armazenamento:** respostas só na sessão; logs registram perfil, cluster e carteira, sem dado identificável.
- **Explicabilidade (art. 20 da LGPD):** pontuação por pergunta, faixas, pesos do modelo e fatores SHAP visíveis.
- **Dados de treino:** anonimizados (`ncodpers` é código); redistribuição proibida → `data/` no `.gitignore`.
- **Regulação (CVM):** recomendação de investimento é atividade regulada; aviso legal permanente (`DISCLAIMER`).
- **Prudência por padrão:** em conflito, vale a resposta mais conservadora; endividamento ou falta de reserva
  bloqueiam ativos de risco.

---

## 14. Limitações conhecidas

| Limitação | Impacto | Mitigação |
|---|---|---|
| Clientes espanhóis, 2015–2016 | Comportamento e produtos diferentes do Brasil | Renda em quintis; mapeamento como **analogia** |
| Um único banco | Posse reflete a política comercial, não a adequação | Modelo limitado às faixas de suitability |
| Snapshot único | Sem "próximo produto" no tempo; MAP@7 não comparável | Avaliação leave-one-out |
| Sem preço, risco ou retorno de ativos | Faixas fixas, sem otimização média-variância | Faixas documentadas e testadas |
| ~25% de renda imputada | Ruído na variável mais importante | Mediana por segmento × idade + flag |
| *Train-serve skew* | Usuário do app ≠ cliente do treino (atividade fixa, segmento por regra, renda por quintil) | Documentado (D16, D27) |
| Referência de renda é do trabalho e bruta (PNAD) | Aposentados e rendas de outras fontes ficam fora da distribuição | Pergunta do app pede renda bruta; documentado (D27) |
| Suitability inspirada, não homologada | Não serve para uso real | Aviso legal |
| Não considera IR, taxas, Selic/IPCA atuais | Carteira simplificada | Declarado |
| Relatórios com caminhos absolutos de Windows nas imagens | Figuras quebradas ao abrir `reports/*.md` fora daquela máquina | Regenerar os relatórios ou usar caminhos relativos (`../docs/figures/…`) |

---

## 15. Convenções de código e como evoluir

### Convenções
- **Idioma:** domínio e regras em português (`calcular_perfil`, `Questionario`); pipeline de dados e ML em
  inglês (`prepare_features`, `train_models`). Mantenha o padrão do módulo que estiver editando.
- **Constantes:** só em `src/config.py`. Nenhum número mágico em outros módulos.
- **Tipagem:** `from __future__ import annotations`, type hints em funções públicas, `@dataclass` para resultados.
- **Logging:** `src.utils.get_logger(__name__)`, nunca `print`.
- **Determinismo:** sempre `random_state=config.RANDOM_STATE`.
- **Decisões:** toda escolha técnica relevante vira uma entrada `Dxx` em `docs/decisoes.md`
  (contexto → decisão → alternativas descartadas).
- **Executáveis:** cada etapa é um módulo com `main()` e roda com `python -m src.<modulo>`.

### Receitas de evolução

| Quero… | Onde mexer | Cuidados |
|---|---|---|
| Mudar faixas de alocação ou pontos | `config.ALLOCATION_BANDS`, `SUITABILITY_POINTS` | Rodar `test_portfolio.py` e personas; Σmín ≤ 100 ≤ Σmáx |
| Adicionar pergunta | `config.py` → `Questionario` → `components.PERGUNTAS`/`ETAPAS` → regra em `portfolio.py` | Precisa mudar uma regra (minimização); bordas das faixas = limites das regras |
| Trocar o modelo de recomendação | `src/recommender.py` (manter `predict_proba`, `recommend`, `explain`) | `portfolio.py` não muda (D22); comparar com os baselines |
| Renomear clusters | `config.CLUSTER_NAME_OVERRIDES` | Após ver o perfil real |
| Atualizar quintis de renda | `config.BR_MONTHLY_INCOME_EDGES`, `BR_TOP_SEGMENT_MIN_INCOME` e `INCOME_BANDS` | SIDRA Tabela 7540 do ano mais recente; o teste de alinhamento das faixas precisa passar |
| Novo campo na tela | `api.serializar()` → `frontend/src/types.ts` → componente | Lógica fica no back-end |

**Checklist antes de entregar uma mudança:** `pytest` verde → `python -m src.pipeline --out ensaio --sample-size 5000`
sem falhas de persona → decisão registrada em `docs/decisoes.md` se for escolha técnica.

---

## 16. Solução de problemas

| Sintoma | Causa | Solução |
|---|---|---|
| `403 Forbidden` no download | Regras da competição não aceitas | Clicar em "I Understand and Accept" no Kaggle |
| Erro ao importar `shap` | numpy 2.x instalado por dependência transitiva | `pip install -r requirements.txt` (versões fixadas) |
| `Artefatos ausentes` / API 503 | Pipeline não executado | `python -m src.pipeline` |
| `y contains previously unseen labels` | Item raríssimo sem positivos na validação | Já tratado (D31); conferir `MIN_POSITIVES_TO_TRAIN` |
| App não reflete mudança em `src/` | Streamlit só recarrega o script principal | Reiniciar o servidor |
| "R640decadaR" no texto | `$` interpretado como LaTeX | Passar o texto por `md()` |
| Front React sem dados | API fora do ar | `uvicorn api.main:app --port 8000` |
| venv falha no Windows | Caminho com mais de 260 caracteres | Projeto em caminho curto |
| Tema do Streamlit não aplicado | Rodou fora da raiz | Rodar na raiz do projeto |

---

## 17. Próximos passos

1. Atualizar os limites de renda a cada nova divulgação da **PNAD Contínua** (SIDRA, Tabela 7540).
2. Dados brasileiros (**Open Finance**, com consentimento) para eliminar a analogia Espanha → Brasil.
3. **Modelo temporal** ("próximo produto" entre meses) usando os 17 meses do arquivo original.
4. **Otimização de carteira** com retornos e riscos históricos (CDI, IMA-B, Ibovespa).
5. **Calibração explícita** (isotônica/Platt) e busca de hiperparâmetros (Optuna).
6. **Texto por LLM** (ex.: Claude) reescrevendo o template **sem permissão para alterar números**.
7. **Monitoramento:** drift das features, taxa de modo proteção e auditoria de viés periódica.

---

## 18. Mapa de arquivos

```
├── api/main.py              # FastAPI: /api/saude, /api/questionario, /api/recomendacao
├── app/
│   ├── main.py              # Streamlit (layout e navegação)
│   └── components.py        # perguntas, validação, avisos, gráfico (sem Streamlit)
├── frontend/                # React + Vite + TS (Inicio, Questionario, Resultado, Rosca)
├── src/
│   ├── config.py            # TODAS as constantes e premissas
│   ├── download_data.py     # Kaggle
│   ├── prepare_data.py      # Etapa 2: chunks, limpeza, amostra, prep_stats.json
│   ├── features.py          # contagens por classe, log renda, ponte de produtos
│   ├── eda.py               # Etapa 3: gráficos e insights
│   ├── segmentation.py      # Etapa 4: K-Means × GMM
│   ├── recommender.py       # Etapa 5: LightGBM, baselines, métricas, SHAP
│   ├── portfolio.py         # Etapa 6: suitability e carteira (SEM ML)
│   ├── advisor.py           # ponte questionário → modelos → regras
│   ├── personas.py          # Etapa 8: aceitação
│   ├── bias_audit.py        # Etapa 8: viés (sexo, idade)
│   ├── pipeline.py          # tudo em um comando
│   └── utils.py             # logging, fmt_brl, fmt_num
├── tests/                   # pytest + dados sintéticos
├── notebooks/01_eda.ipynb
├── docs/
│   ├── decisoes.md          # D1–D38
│   ├── limitacoes.md
│   ├── roteiro_apresentacao.md
│   └── figures/             # 11–18 versionadas
├── reports/                 # qualidade, segmentação, recomendação, personas, viés
├── data/                    # raw/ e processed/ não versionados; external/ = tabelas do IBGE
└── models/                  # não versionado (*.joblib, prep_stats.json)
```
