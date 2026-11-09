output "url_local" {
  description = "Endereço do app neste computador."
  value       = "http://localhost:${var.porta}"
}

output "link_publico" {
  description = "Como ver o endereço público gerado pelo túnel (só com link_publico = true)."
  value       = var.link_publico ? "docker logs ${var.nome}-tunel 2>&1 | Select-String trycloudflare   (no Linux/macOS: | grep trycloudflare)" : "desligado (use -var link_publico=true)"
}

output "pasta_modelos" {
  description = "Pasta montada em /models no contêiner."
  value       = local.pasta_modelos
}
