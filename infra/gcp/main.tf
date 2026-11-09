# Deploy no Google Cloud dentro da cota grátis (D38):
#   Artifact Registry (imagem) + Cloud Storage (modelos) + Cloud Run (API + front).
# O Cloud Run desliga quando ninguém usa (min 0 instâncias) e o bucket é montado
# somente leitura em /models, que é para onde aponta ASSESSOR_MODELS_DIR na imagem.

locals {
  imagem = "${var.regiao}-docker.pkg.dev/${var.projeto}/${google_artifact_registry_repository.imagens.repository_id}/${var.nome}:${var.imagem_tag}"

  apis = concat(
    ["run.googleapis.com", "artifactregistry.googleapis.com", "storage.googleapis.com", "iam.googleapis.com"],
    var.conta_faturamento == "" ? [] : ["billingbudgets.googleapis.com"],
  )
}

resource "google_project_service" "apis" {
  for_each           = toset(local.apis)
  service            = each.value
  disable_on_destroy = false
}

# ---------------------------------------------------------------------------
# Imagens (Artifact Registry): cota grátis de 0,5 GB e a imagem tem ~280 MB comprimida
# → guarda só a versão mais recente (a que está no ar). A limpeza roda uma vez por dia.
# ---------------------------------------------------------------------------
resource "google_artifact_registry_repository" "imagens" {
  repository_id = var.nome
  location      = var.regiao
  format        = "DOCKER"
  description   = "Imagens do Assessor de Investimentos Virtual"

  cleanup_policy_dry_run = false
  cleanup_policies {
    id     = "manter-a-ultima"
    action = "KEEP"
    most_recent_versions {
      keep_count = 1
    }
  }
  cleanup_policies {
    id     = "apagar-antigas"
    action = "DELETE"
    condition {
      tag_state = "ANY"
    }
  }

  depends_on = [google_project_service.apis]
}

# ---------------------------------------------------------------------------
# Modelos (Cloud Storage): privado; só a conta de serviço do Cloud Run lê
# ---------------------------------------------------------------------------
resource "google_storage_bucket" "modelos" {
  name                        = "${var.projeto}-${var.nome}-modelos"
  location                    = upper(var.regiao)
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = true # terraform destroy apaga também os modelos enviados

  depends_on = [google_project_service.apis]
}

resource "google_service_account" "api" {
  account_id   = "${var.nome}-api"
  display_name = "Assessor - API no Cloud Run"
  depends_on   = [google_project_service.apis]
}

resource "google_storage_bucket_iam_member" "api_le_modelos" {
  bucket = google_storage_bucket.modelos.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.api.email}"
}

# ---------------------------------------------------------------------------
# Serviço (Cloud Run) — criado só depois que a imagem existe (imagem_tag != "")
# ---------------------------------------------------------------------------
resource "google_cloud_run_v2_service" "api" {
  count               = var.imagem_tag == "" ? 0 : 1
  name                = var.nome
  location            = var.regiao
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = false

  template {
    service_account                  = google_service_account.api.email
    execution_environment            = "EXECUTION_ENVIRONMENT_GEN2" # necessário para montar o bucket
    max_instance_request_concurrency = 20
    timeout                          = "60s"

    scaling {
      min_instance_count = 0 # desliga sem uso: não consome cota parado
      max_instance_count = var.max_instancias
    }

    containers {
      image = local.imagem

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = "1"
          memory = var.memoria
        }
        cpu_idle          = true  # CPU cobrada só durante as requisições
        startup_cpu_boost = false # o boost consome cota extra na partida
      }

      env {
        name  = "ASSESSOR_MODELS_DIR"
        value = "/models"
      }

      volume_mounts {
        name       = "modelos"
        mount_path = "/models"
      }

      startup_probe {
        tcp_socket {
          port = 8080
        }
        initial_delay_seconds = 0
        period_seconds        = 5
        failure_threshold     = 24 # até 2 min para importar as bibliotecas
      }
    }

    volumes {
      name = "modelos"
      gcs {
        bucket    = google_storage_bucket.modelos.name
        read_only = true
      }
    }
  }

  depends_on = [google_storage_bucket_iam_member.api_le_modelos]
}

# Acesso público ao site (sem login), como no app local.
resource "google_cloud_run_v2_service_iam_member" "publico" {
  count    = length(google_cloud_run_v2_service.api)
  name     = google_cloud_run_v2_service.api[0].name
  location = var.regiao
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# ---------------------------------------------------------------------------
# Alerta de orçamento (opcional): e-mail aos administradores do faturamento
# ---------------------------------------------------------------------------
data "google_project" "atual" {}

resource "google_billing_budget" "alerta" {
  count           = var.conta_faturamento == "" ? 0 : 1
  billing_account = var.conta_faturamento
  display_name    = "${var.nome} - alerta de gastos"

  budget_filter {
    projects = ["projects/${data.google_project.atual.number}"]
  }

  amount {
    specified_amount {
      units = tostring(var.orcamento_brl)
    }
  }

  threshold_rules {
    threshold_percent = 0.01 # avisa no primeiro centavo: o esperado é gasto zero
  }
  threshold_rules {
    threshold_percent = 1.0
  }

  depends_on = [google_project_service.apis]
}
