output "url" {
  description = "Endereço público do app (vazio até o serviço ser criado com imagem_tag)."
  value       = length(google_cloud_run_v2_service.api) > 0 ? google_cloud_run_v2_service.api[0].uri : ""
}

output "repositorio_imagens" {
  description = "Para onde enviar a imagem: docker push <repositorio_imagens>/assessor:<tag>"
  value       = "${var.regiao}-docker.pkg.dev/${var.projeto}/${google_artifact_registry_repository.imagens.repository_id}"
}

output "bucket_modelos" {
  description = "Bucket onde vão os arquivos da pasta models/."
  value       = "gs://${google_storage_bucket.modelos.name}"
}
