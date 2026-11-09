# Deploy no Google Cloud com Terraform (cota grátis)

Sobe o app (API FastAPI + front React) no **Cloud Run**, com os modelos num bucket do **Cloud Storage**
e a imagem no **Artifact Registry**. A escolha e os limites estão na decisão D38 (`docs/decisoes.md`).
Sem conta de faturamento? Use [`infra/docker`](../docker/README.md), que roda no Docker local.

```
Usuário ──► Cloud Run (contêiner: uvicorn api.main:app + frontend/dist)
                 │  monta somente leitura em /models
                 ▼
            Cloud Storage  gs://<projeto>-assessor-modelos   (segmentation.joblib, recommender.joblib,
                                                              prep_stats.json, raio_x.json)
Imagem  ──► Artifact Registry  us-central1-docker.pkg.dev/<projeto>/assessor/assessor:<tag>
```

## Por que sai de graça

| Recurso | Cota grátis mensal (Google, sem prazo) | Uso esperado |
|---|---|---|
| Cloud Run | 2 milhões de requisições, 180 mil vCPU-s, 360 mil GiB-s | demonstração: muito abaixo |
| Artifact Registry | 0,5 GB | 1 imagem de ~280 MB (a limpeza apaga as antigas) |
| Cloud Storage | 5 GB em `us-central1`/`us-east1`/`us-west1` | modelos: poucos MB |

- **Mínimo de 0 instâncias:** sem visitas o contêiner desliga e não gasta nada. O 1º acesso
  depois de um tempo parado leva alguns segundos, para importar as bibliotecas e carregar os
  modelos. Abra o site um minuto antes de apresentar.
- **Máximo de 1 instância:** o custo não escala sozinho.
- **Alerta de orçamento opcional:** e-mail no primeiro centavo gasto. Ele avisa, mas não bloqueia.
- Confira os valores atuais em <https://cloud.google.com/free>. O Google exige cartão
  cadastrado mesmo para usar só a cota grátis.

## Pré-requisitos (uma vez)

1. Instale o [Google Cloud CLI](https://cloud.google.com/sdk/docs/install) e o
   [Terraform ≥ 1.6](https://developer.hashicorp.com/terraform/install).
2. Para montar a imagem, use **uma** das opções: o [Docker Desktop](https://www.docker.com/products/docker-desktop/)
   ou o Cloud Build (opção B do passo 4, que dispensa Docker local).
3. Tenha os modelos treinados na pasta `models/` (`python -m src.pipeline`).

## Passo a passo (PowerShell, na raiz do projeto)

### 1. Projeto e login

```powershell
gcloud auth login
gcloud auth application-default login          # credencial que o Terraform usa
gcloud projects create assessor-tcc-123456     # escolha um ID único
gcloud billing accounts list                   # anote o ACCOUNT_ID
gcloud billing projects link assessor-tcc-123456 --billing-account=XXXXXX-XXXXXX-XXXXXX
gcloud config set project assessor-tcc-123456
```

### 2. Primeiro apply: repositório de imagens e bucket

```powershell
cd infra\gcp
copy terraform.tfvars.example terraform.tfvars   # preencha projeto (e conta_faturamento, se quiser o alerta)
terraform init
terraform apply                                   # imagem_tag ainda vazio: não cria o Cloud Run
```

### 3. Enviar os modelos

```powershell
$BUCKET = terraform output -raw bucket_modelos
gcloud storage cp ..\..\models\*.joblib ..\..\models\*.json $BUCKET/
```

### 4. Montar e enviar a imagem

```powershell
$REPO = terraform output -raw repositorio_imagens
cd ..\..
```

**Opção A, com Docker Desktop:**

```powershell
gcloud auth configure-docker us-central1-docker.pkg.dev
docker build -t "$REPO/assessor:v1" .
docker push "$REPO/assessor:v1"
```

**Opção B, com Cloud Build (sem Docker local).** O Cloud Build tem cota grátis mensal de minutos de build:

```powershell
gcloud services enable cloudbuild.googleapis.com
gcloud builds submit --tag "$REPO/assessor:v1" .
```

### 5. Segundo apply: sobe o site

Em `terraform.tfvars`, coloque `imagem_tag = "v1"` e rode:

```powershell
cd infra\gcp
terraform apply
terraform output url        # endereço público do app
```

Abra `<url>/api/saude`. Ele deve responder `{"modelos": true, ...}`.

## Atualizar

- **Mudou o código:** monte e envie com uma tag nova (`v2`), troque `imagem_tag` e rode `terraform apply`.
- **Retreinou os modelos:** repita o passo 3. Um contêiner já ligado mantém os modelos antigos na
  memória. Para recarregar, rode `terraform apply` com uma tag nova ou espere ele desligar sem uso.
- As versões do `requirements-deploy.txt` precisam ser iguais às do `requirements.txt`, senão os
  `.joblib` não carregam. O teste `tests/test_deploy.py` verifica isso.

## Derrubar tudo

```powershell
terraform destroy      # apaga o Cloud Run, o bucket (com os modelos) e o repositório de imagens
```

## Problemas comuns

- **`/api/saude` com `"modelos": false`:** os arquivos não estão na raiz do bucket. Rode
  `gcloud storage ls $BUCKET` para conferir.
- **Erro de memória nos logs:** aumente `memoria` (ex.: `"4Gi"`). Isso consome a cota mais rápido.
- **`allUsers` bloqueado:** contas de organização (ex.: e-mail da faculdade) podem proibir acesso
  público. Use uma conta Google pessoal.
- **Estado do Terraform:** fica em `terraform.tfstate` nesta pasta, fora do git. Não apague. Para
  trabalhar em equipe, mova o estado para um bucket (`backend "gcs"`).
