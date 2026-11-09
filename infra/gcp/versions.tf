terraform {
  required_version = ">= 1.6"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }

  # Estado local (terraform.tfstate nesta pasta, fora do git). Para um projeto acadêmico
  # com uma pessoa aplicando, basta. Em equipe, use um backend "gcs" (ver README).
}

provider "google" {
  project = var.projeto
  region  = var.regiao

  # A API de orçamentos (billingbudgets) exige um projeto de cota quando se usa a
  # credencial de usuário (gcloud auth application-default login).
  user_project_override = true
  billing_project       = var.projeto
}
