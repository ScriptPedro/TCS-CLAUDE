# Deploy com Terraform no Docker (local, grátis, sem cartão)

O Terraform monta a imagem do app a partir do `Dockerfile` da raiz e sobe o contêiner no
**Docker do seu computador**. Opcionalmente, ele também cria um **link público temporário**
para a banca acessar de outro computador ou do celular. A escolha está na decisão D39
(`docs/decisoes.md`). Para publicar numa nuvem, veja [`infra/gcp`](../gcp/README.md).

```
Terraform ──► docker_image "assessor:local"   (build do Dockerfile: front React + API FastAPI)
          ──► docker_network "assessor"
          ──► docker_container "assessor"      http://localhost:8080
                    ├─ models/ montada somente leitura em /models
                    └─ volume "assessor-usuarios" em /app/data (banco de usuários, D40)
          ──► docker_container "assessor-tunel"  (opcional) https://<aleatório>.trycloudflare.com
```

## Pré-requisitos

1. [Docker Desktop](https://www.docker.com/products/docker-desktop/) instalado e **aberto** (ícone da
   baleia "running").
2. Terraform ≥ 1.6:

   ```powershell
   winget install Hashicorp.Terraform
   ```

3. Modelos treinados em `models/`: `segmentation.joblib`, `recommender.joblib`, `prep_stats.json`
   e, se houver, `raio_x.json`. Para gerar, rode `python -m src.pipeline`.

## Subir (PowerShell)

```powershell
cd infra\docker
terraform init
terraform apply
```

O primeiro `apply` monta a imagem e leva alguns minutos. Ele só termina quando a API responde com os
modelos carregados. Depois, abra **http://localhost:8080**.

## Link público para a apresentação

```powershell
terraform apply -var link_publico=true
docker logs assessor-tunel 2>&1 | Select-String trycloudflare
```

O endereço `https://...trycloudflare.com` que aparecer funciona de qualquer lugar.

- **Temporário:** o endereço muda toda vez que o túnel reinicia.
- **Depende do seu computador:** só funciona com o computador ligado e o Docker aberto.
- **Sem garantia de disponibilidade:** é um serviço gratuito do Cloudflare, sem conta. Teste antes
  da apresentação e tenha o `localhost` como plano B.

Para desligar só o link: `terraform apply` (sem a variável).

## Primeiro administrador

O cadastro pela tela cria só usuários comuns. Depois do primeiro `apply`, crie o administrador
dentro do contêiner:

```powershell
docker exec -it assessor python -m api.usuarios criar-admin
```

Os usuários ficam no volume `assessor-usuarios`. Eles sobrevivem a um novo `apply`, à troca do
contêiner e ao `terraform destroy`.

## Atualizar

- **Mudou o código** (`src/`, `app/`, `api/`, `frontend/`, `Dockerfile`): rode `terraform apply`. O
  Terraform percebe a mudança, monta a imagem de novo e troca o contêiner.
- **Retreinou os modelos:** rode `docker restart assessor`. Os arquivos já estão montados; o
  restart só faz a API recarregá-los.

## Derrubar

```powershell
terraform destroy      # remove contêineres e rede (a imagem fica em cache para o próximo apply)
```

O volume com os usuários **não** é apagado pelo `destroy`. Para começar do zero, apague-o à mão:

```powershell
docker volume rm assessor-usuarios
```

## Variáveis

| Variável | Padrão | Para quê |
|---|---|---|
| `porta` | `8080` | Porta no computador (`http://localhost:<porta>`). |
| `pasta_modelos` | `models/` do projeto | Outra pasta com os modelos. |
| `link_publico` | `false` | Sobe o túnel do Cloudflare. |
| `docker_host` | detecta | Força o endereço do Docker (ex.: `tcp://localhost:2375`). |

Para não repetir variáveis na linha de comando, copie `terraform.tfvars.example` para `terraform.tfvars`.

## Problemas comuns

- **`Faltam modelos em ...`:** rode o pipeline ou aponte `pasta_modelos` para onde os arquivos estão.
- **`Cannot connect to the Docker daemon` / `npipe`:** abra o Docker Desktop e espere ele ficar "running".
- **`port is already allocated`:** outra coisa usa a 8080 (ex.: um `uvicorn` aberto). Feche-a ou use
  `-var porta=8081`.
- **O apply passou de 3 minutos esperando o contêiner:** veja o motivo com `docker logs assessor`.
  Geralmente são modelos treinados com versões diferentes do `requirements.txt`.
