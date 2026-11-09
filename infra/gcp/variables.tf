variable "projeto" {
  description = "ID do projeto no Google Cloud (ex.: assessor-tcc-123456). Precisa ter faturamento vinculado."
  type        = string
}

variable "regiao" {
  description = "Região. us-central1 entra na cota grátis do Cloud Storage; São Paulo (southamerica-east1) não."
  type        = string
  default     = "us-central1"
}

variable "nome" {
  description = "Prefixo dos recursos (serviço do Cloud Run, repositório de imagens, bucket)."
  type        = string
  default     = "assessor"
}

variable "imagem_tag" {
  description = <<-EOT
    Tag da imagem já enviada ao Artifact Registry (ex.: v1). Vazio = cria só o repositório
    de imagens e o bucket (1º apply); o serviço do Cloud Run é criado quando a tag é informada.
  EOT
  type        = string
  default     = ""
}

variable "memoria" {
  description = "Memória do contêiner. LightGBM + SHAP + modelos carregados pedem ~1 GiB; 2Gi dá folga."
  type        = string
  default     = "2Gi"
}

variable "max_instancias" {
  description = "Máximo de instâncias. 1 impede que o custo escale além da cota grátis."
  type        = number
  default     = 1
}

variable "conta_faturamento" {
  description = <<-EOT
    ID da conta de faturamento (ex.: 0X0X0X-0X0X0X-0X0X0X) para criar o alerta de orçamento.
    Vazio = não cria o alerta. Veja com: gcloud billing accounts list
  EOT
  type        = string
  default     = ""
}

variable "orcamento_brl" {
  description = "Valor do alerta de orçamento, na moeda da conta de faturamento. Avisa por e-mail; não bloqueia gastos."
  type        = number
  default     = 5
}
