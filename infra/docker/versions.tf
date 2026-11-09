terraform {
  required_version = ">= 1.6"

  required_providers {
    docker = {
      source  = "kreuzwerker/docker"
      version = "~> 3.6"
    }
  }

  # Estado local (terraform.tfstate nesta pasta, fora do git).
}

provider "docker" {
  host = local.docker_host
}
