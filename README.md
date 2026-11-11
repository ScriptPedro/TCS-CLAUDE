# Assessor de Investimentos Virtual

Projeto final de IA Aplicada (BFSI). O usuário responde a um questionário e recebe:

1. o **segmento de cliente** em que se encaixa (K-Means);
2. os **produtos** mais comuns entre clientes parecidos, com probabilidade e motivo (LightGBM + SHAP);
3. uma **carteira sugerida** por classe de ativo brasileira (motor de suitability + modelo);
4. uma **explicação** em linguagem simples.

> ⚠️ **Aviso:** projeto acadêmico. Não constitui recomendação de investimento.
> Os modelos são treinados com dados de clientes espanhóis (2015–2016).

## Arquitetura

```
                    ┌──────────────── Questionário (app/main.py) ────────────────┐
                    │ idade · renda · cartão · reserva · objetivo · prazo ·      │
                    │ tolerância · produtos que já tem · tempo de conta          │
                    └──────────────┬──────────────────────────────┬──────────────┘
                                   │ src/advisor.py (ponte, D16)   │
             ┌─────────────────────▼──────────┐   ┌───────────────▼────────────────────┐
             │ IA (aprendida dos dados)       │   │ REGRAS DE NEGÓCIO (src/portfolio)  │
             │ • K-Means → segmento           │   │ • pontuação de suitability + tetos │
             │ • LightGBM → P(item) por item  │   │ • modo proteção (cartão/reserva)   │
             │ • SHAP → por quê               │   │ • faixas (mín, máx) por perfil     │
             └─────────────────────┬──────────┘   └───────────────┬────────────────────┘
                                   └──────────┐       ┌───────────┘
                                         ┌────▼───────▼─────┐
                                         │ alocar(): o perfil│
                                         │ define a FAIXA; o │
                                         │ modelo, a POSIÇÃO │
                                         └────────┬─────────┘
                                   carteira % + produtos + explicação
```

## Estrutura

```
assessor-investimentos/
├── api/
│   ├── main.py            # FastAPI do front React (questionário, recomendação)
│   ├── usuarios.py        # login, cadastro e gerenciamento de usuários (D40)
│   ├── banco.py           # banco SQLite dos usuários (SQL puro, soft delete, sessões)
│   └── validacao.py       # validação de CPF, nome, idade, e-mail e senha
├── app/
│   ├── main.py            # Etapa 7 — Streamlit (layout e navegação)
│   └── components.py      # validação do formulário, gráfico (testáveis sem Streamlit)
├── data/raw/              # train_ver2.csv e microdados do Raio X (não versionados)
├── data/processed/        # santander_50k.parquet, santander_50k_clusters.parquet
├── data/usuarios.db       # banco de usuários do front React (criado sozinho, não versionado)
├── docs/
│   ├── decisoes.md        # D1–D40: cada decisão técnica e as alternativas descartadas
│   ├── limitacoes.md      # limitações, vieses, ética/LGPD, próximos passos
│   ├── roteiro_apresentacao.md  # roteiro de 13 min + perguntas prováveis da banca
│   └── figures/           # figuras 01–18 para os slides
├── infra/docker/         # Terraform: sobe o app no Docker local, com link público opcional (D39)
├── infra/gcp/            # Terraform: Google Cloud Run na cota grátis (D38); Dockerfile na raiz
├── models/                # segmentation.joblib, recommender.joblib, prep_stats.json, raio_x.json
├── notebooks/01_eda.ipynb # Etapa 3
├── reports/               # qualidade, segmentação, recomendação, Raio X, personas, auditoria de viés
├── src/
│   ├── config.py          # TODAS as constantes e premissas
│   ├── download_data.py   # download via API do Kaggle
│   ├── prepare_data.py    # Etapa 2 — leitura em chunks, limpeza, amostra
│   ├── features.py        # contagens por classe, log renda, ponte do questionário
│   ├── eda.py             # Etapa 3 — gráficos e insights calculados
│   ├── segmentation.py    # Etapa 4 — K-Means × GMM
│   ├── recommender.py     # Etapa 5 — LightGBM, baselines, métricas, SHAP
│   ├── raio_x.py          # referência brasileira: posse por renda × idade (Raio X ANBIMA, D36)
│   ├── portfolio.py       # Etapa 6 — suitability e carteira (SEM ML)
│   ├── advisor.py         # orquestra questionário → modelos → regras
│   ├── personas.py        # Etapa 8 — personas com saídas esperadas
│   ├── bias_audit.py      # Etapa 8 — auditoria de viés (sexo, idade)
│   ├── pipeline.py        # tudo em um comando
│   └── utils.py           # logging, formatação brasileira de números
└── tests/                 # ~200 testes (pytest), incluindo app e pipeline ponta a ponta
```

## Instalação (Windows / PowerShell)

> Use **sempre** o ambiente virtual `.venv` com Python 3.11, nunca o Python global. Passo a passo,
> verificação e erros comuns: [`skills/ambiente-virtual/SKILL.md`](skills/ambiente-virtual/SKILL.md).

Crie o projeto num **caminho curto** (ex.: `C:\projetos\assessor`): o Windows limita caminhos a
260 caracteres, e o venv pode falhar em pastas muito profundas.

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Download dos dados (Kaggle)

1. Crie uma conta em [kaggle.com](https://www.kaggle.com).
2. Abra a [página da competição](https://www.kaggle.com/competitions/santander-product-recommendation/rules)
   e clique em **"I Understand and Accept"**. Sem isso a API retorna **403 Forbidden**.
3. Em **Settings → API → Create New Token**, salve o `kaggle.json` em `C:\Users\<seu_usuario>\.kaggle\`.
4. Baixe:

```powershell
python -m src.download_data
```

## Referência brasileira (Raio X ANBIMA, opcional)

A carteira usa também a posse real de produtos entre brasileiros da mesma renda e idade (D36).

1. Na [página do Raio X do Investidor Brasileiro](https://www.anbima.com.br/pt_br/especial/raio-x-do-investidor-brasileiro.htm),
   baixe os **dados brutos** da 9ª edição (2026).
2. Salve `DADOS BRUTOS RAIO X 2026.xlsx` em `data/raw/`.
3. Rode `python -m src.raio_x` (ou o pipeline completo). Isso gera `models/raio_x.json` e `reports/raio_x.md`.

Sem esse arquivo o app funciona normalmente, só com o modelo.

## Executando

**Tudo de uma vez** (preparação → segmentação → recomendação → Raio X → personas → auditoria):

```powershell
python -m src.pipeline
```

Ou etapa por etapa:

| Etapa | Comando | Saída principal |
|------|---------|-------|
| 2. Preparação | `python -m src.prepare_data` | `data/processed/santander_50k.parquet`, `reports/qualidade_dados.md` |
| 3. EDA | `jupyter lab notebooks/01_eda.ipynb` | figuras 01–10 |
| 4. Segmentação | `python -m src.segmentation` | `models/segmentation.joblib`, figuras 11–14 |
| 5. Recomendação | `python -m src.recommender` | `models/recommender.joblib`, figuras 15–18 |
| Referência BR | `python -m src.raio_x` | `models/raio_x.json`, `reports/raio_x.md` |
| 8. Personas | `python -m src.personas` | `reports/personas.md` |
| 8. Auditoria | `python -m src.bias_audit` | `reports/auditoria_vies.md` |
| 7. App (Streamlit) | `streamlit run app/main.py` | http://localhost:8501 |
| 7. App (React) | ver [Front React](#front-react) | http://localhost:5173 |
| Testes | `pytest` | — |

**Ensaio isolado** (não toca em `data/`, `models/` nem `reports/`): `python -m src.pipeline --out ensaio --sample-size 5000`.

### Sobre o app

- Rode na **raiz do projeto** (assim o tema em `.streamlit/config.toml` é aplicado).
- Para usar modelos de outra pasta: `$env:ASSESSOR_MODELS_DIR = "C:\caminho"; streamlit run app/main.py`.
  A pasta precisa conter `segmentation.joblib`, `recommender.joblib` e `prep_stats.json` (e, opcionalmente, `raio_x.json`).
- Ao alterar arquivos em `src/`, **reinicie** o servidor: o Streamlit só recarrega o script principal.

### Front React

Interface nova em `frontend/` (React + Vite + TypeScript), servida pela API `api/main.py` (FastAPI).
A API reaproveita `app/components.py` e `src/advisor.py`: nenhuma regra foi duplicada no front.
Requer [Node.js](https://nodejs.org) 18 ou superior.

Em dois terminais, na raiz do projeto:

```powershell
uvicorn api.main:app --reload --port 8000      # terminal 1: API
cd frontend; npm install; npm run dev          # terminal 2: front em http://localhost:5173
```

**Login.** O front abre numa tela de entrada (e-mail ou CPF + senha) com a aba **Criar conta**.
O cadastro pela tela cria sempre um usuário comum. Crie o primeiro administrador pela linha de comando:

```powershell
python -m api.usuarios criar-admin             # pergunta nome, CPF, e-mail, idade e senha
```

O administrador encontra **Conta → Gerenciar usuários**, onde pode cadastrar, editar, excluir
(soft delete) e restaurar contas. O banco é `data/usuarios.db`. Para usar outro arquivo, defina
`ASSESSOR_DB`. No contêiner, rode o mesmo comando com `docker exec -it <contêiner> python -m api.usuarios criar-admin`.

Para apresentar com um único servidor: `cd frontend; npm run build` e depois só a API
(`uvicorn api.main:app --port 8000`), que passa a servir o front em http://localhost:8000.

### Publicar na nuvem

O `Dockerfile` empacota a API e o front num só contêiner, e o Terraform sobe esse contêiner:

- **[infra/docker](infra/docker/README.md):** no Docker do próprio computador, grátis e sem cartão, com
  link público temporário opcional para a banca (D39). Basta `cd infra\docker; terraform init; terraform apply`.
- **[infra/gcp](infra/gcp/README.md):** no Google Cloud Run, dentro da cota grátis, com os modelos num
  bucket (D38). Exige conta de faturamento ativa.

## Tempo esperado

Num notebook comum: leitura do CSV de 2,3 GB em chunks, poucos minutos; segmentação com k = 2..10 em
50 mil clientes (K-Means + GMM), alguns minutos; recomendação e SHAP, menos de 1 minuto. Em dados
sintéticos com 10 mil clientes, o pipeline completo levou ~21 s.

## Premissas principais

- **50.000 clientes únicos** do snapshot `2016-05-28`, estratificados por `segmento`, `random_state=42` (D1).
- Renda tratada por **posição relativa** (quintis), não convertida para BRL (D3, D27).
- Perguntas sem correspondência no dataset viram **regras de negócio**, não features (D4, D22).
- `sexo` fica fora de todos os modelos e não é perguntado no app; é usado só na auditoria de viés (D11).

## Documentação

- [Decisões técnicas (D1–D40)](docs/decisoes.md)
- [Deploy com Terraform no Docker local](infra/docker/README.md)
- [Deploy com Terraform no Google Cloud (cota grátis)](infra/gcp/README.md)
- [Limitações, vieses, ética e próximos passos](docs/limitacoes.md)
- [Roteiro de apresentação e perguntas da banca](docs/roteiro_apresentacao.md)
