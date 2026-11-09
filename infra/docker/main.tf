# Deploy com Terraform no Docker do próprio computador (D39): sem nuvem, sem cartão.
# O Terraform monta a imagem a partir do Dockerfile da raiz, cria uma rede, sobe o
# contêiner da API (que também serve o front React) com a pasta models/ montada em
# /models e, se pedido, um túnel do Cloudflare com um endereço público temporário.

locals {
  raiz = abspath("${path.module}/../..")

  # No Windows o abspath começa com a letra do disco (C:/...); no Linux/macOS, com "/".
  windows     = !startswith(local.raiz, "/")
  docker_host = var.docker_host != "" ? var.docker_host : (local.windows ? "npipe:////./pipe/docker_engine" : "unix:///var/run/docker.sock")

  pasta_modelos = abspath(var.pasta_modelos != "" ? var.pasta_modelos : "${local.raiz}/models")
  obrigatorios  = ["segmentation.joblib", "recommender.joblib", "prep_stats.json"]
  faltando      = [for f in local.obrigatorios : f if !fileexists("${local.pasta_modelos}/${f}")]

  # Hash do que entra na imagem: se o código mudar, o próximo apply monta a imagem de novo.
  arquivos_imagem = concat(
    ["Dockerfile", ".dockerignore", "requirements-deploy.txt"],
    tolist(fileset(local.raiz, "src/**/*.py")),
    tolist(fileset(local.raiz, "app/**/*.py")),
    tolist(fileset(local.raiz, "api/**/*.py")),
    tolist(fileset(local.raiz, "frontend/src/**")),
    tolist(fileset(local.raiz, "frontend/*.{json,ts,html}")),
    tolist(fileset(local.raiz, "frontend/public/**")),
  )
  hash_codigo = sha1(join("", [for f in sort(local.arquivos_imagem) : filesha1("${local.raiz}/${f}")]))
}

resource "docker_network" "rede" {
  name = var.nome
}

resource "docker_image" "app" {
  name         = "${var.nome}:local"
  keep_locally = true

  build {
    context    = local.raiz
    dockerfile = "Dockerfile"
    tag        = ["${var.nome}:local"]
  }

  triggers = {
    codigo = local.hash_codigo
  }
}

resource "docker_container" "app" {
  name    = var.nome
  image   = docker_image.app.image_id
  restart = "unless-stopped"
  env     = ["ASSESSOR_MODELS_DIR=/models"]

  ports {
    internal = 8080
    external = var.porta
  }

  volumes {
    host_path      = local.pasta_modelos
    container_path = "/models"
    read_only      = true
  }

  networks_advanced {
    name = docker_network.rede.id
  }

  # O apply só termina quando a API responde; se os modelos não carregarem, o erro aparece aqui.
  healthcheck {
    test         = ["CMD", "python", "-c", "import json,urllib.request as u; assert json.load(u.urlopen('http://localhost:8080/api/saude'))['modelos']"]
    interval     = "15s"
    timeout      = "10s"
    start_period = "1m0s"
    retries      = 3
  }
  wait         = true
  wait_timeout = 180

  lifecycle {
    precondition {
      condition     = length(local.faltando) == 0
      error_message = "Faltam modelos em ${local.pasta_modelos}: ${join(", ", local.faltando)}. Rode antes: python -m src.pipeline (ou informe pasta_modelos)."
    }
  }
}

# ---------------------------------------------------------------------------
# Link público opcional (túnel rápido do Cloudflare, sem conta e sem cartão)
# ---------------------------------------------------------------------------
resource "docker_image" "cloudflared" {
  count        = var.link_publico ? 1 : 0
  name         = var.imagem_cloudflared
  keep_locally = true
}

resource "docker_container" "tunel" {
  count   = var.link_publico ? 1 : 0
  name    = "${var.nome}-tunel"
  image   = docker_image.cloudflared[0].image_id
  restart = "unless-stopped"
  command = ["tunnel", "--no-autoupdate", "--url", "http://${docker_container.app.name}:8080"]

  networks_advanced {
    name = docker_network.rede.id
  }
}
