variable "nome" {
  description = "Nome do contêiner, da imagem e da rede Docker."
  type        = string
  default     = "assessor"
}

variable "porta" {
  description = "Porta do computador onde o app fica disponível (http://localhost:<porta>)."
  type        = number
  default     = 8080
}

variable "pasta_modelos" {
  description = <<-EOT
    Pasta com segmentation.joblib, recommender.joblib, prep_stats.json (e raio_x.json, opcional).
    Vazio = a pasta models/ do projeto. Ela é montada somente leitura em /models no contêiner.
  EOT
  type        = string
  default     = ""
}

variable "link_publico" {
  description = <<-EOT
    true = sobe também um túnel gratuito do Cloudflare (sem conta) e gera um endereço
    https://<aleatório>.trycloudflare.com para acessar o app de outro computador ou do celular.
    O endereço muda a cada vez que o túnel reinicia e só funciona com este computador ligado.
  EOT
  type        = bool
  default     = false
}

variable "imagem_cloudflared" {
  description = "Imagem do túnel do Cloudflare (versão fixada para o resultado ser reproduzível)."
  type        = string
  default     = "cloudflare/cloudflared:2026.10.4"
}

variable "docker_host" {
  description = <<-EOT
    Endereço do Docker. Vazio = detecta pelo sistema: Docker Desktop no Windows
    (npipe:////./pipe/docker_engine) ou socket no Linux/macOS (unix:///var/run/docker.sock).
  EOT
  type        = string
  default     = ""
}
