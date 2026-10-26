# Relatório do modelo de recomendação

Treino: 40.000 clientes · teste: 10.000 · itens: Poupança, CDB / depósito a prazo, Fundos de investimento, Ações / valores mobiliários, Previdência privada.

**Sem modelo (menos de 50 clientes possuem; usam a taxa média, D31):** Poupança.

## Comparação com baselines

| modelo | auc_media | precision@1 | map@1 | precision@3 | map@3 | precision@7 | map@7 | loo_hit@1 | loo_hit@3 | loo_mrr |
|---|---|---|---|---|---|---|---|---|---|---|
| LightGBM | 0.846 | 0.527 | 0.527 | 0.333 | 0.647 | 0.239 | 0.695 | 0.551 | 0.928 | 0.736 |
| Popular no cluster | 0.780 | 0.512 | 0.512 | 0.359 | 0.682 | 0.239 | 0.710 | 0.475 | 0.929 | 0.696 |
| Popular global | 0.500 | 0.512 | 0.512 | 0.359 | 0.682 | 0.239 | 0.710 | 0.475 | 0.929 | 0.696 |

- `precision@k` / `map@k`: ranqueando os 5 itens por probabilidade (clientes com ≥ 1 item). Com 5 itens, MAP@7 = MAP@5.
- `loo_*`: um item possuído é escondido; mede se ele aparece no topo entre os itens que o cliente "não tem". É o cenário real do app.

![Comparação](C:/Users/Aluno/Downloads/acessor-investimento/scratch-2026-10-26-396de3/assessor-investimentos/docs/figures/15_comparacao_modelos.png)

## AUC por item

| index | LightGBM | Popular no cluster | Popular global |
|---|---|---|---|
| Poupança | 0.500 | 0.838 | 0.500 |
| CDB / depósito a prazo | 0.945 | 0.734 | 0.500 |
| Fundos de investimento | 0.932 | 0.776 | 0.500 |
| Ações / valores mobiliários | 0.918 | 0.766 | 0.500 |
| Previdência privada | 0.934 | 0.788 | 0.500 |

![AUC](C:/Users/Aluno/Downloads/acessor-investimento/scratch-2026-10-26-396de3/assessor-investimentos/docs/figures/16_auc_por_item.png)

## Explicabilidade (SHAP)

| index | Idade | Renda | Tempo de conta | Cliente ativo | Segmento | Já tem conta corrente / digital | Já tem poupança | Já tem CDB / depósito a prazo | Já tem fundos de investimento | Já tem ações / valores mobiliários | Já tem previdência privada | Já tem cartão de crédito | Já tem empréstimo / financiamento |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| CDB / depósito a prazo | 0.396 | 0.050 | 0.163 | 1.674 | 0.201 | 0.063 | 0.000 | nan | 0.014 | 0.009 | 0.002 | 0.009 | 0.005 |
| Fundos de investimento | 0.415 | 0.183 | 0.439 | 1.384 | 0.131 | 0.060 | 0.000 | 0.040 | nan | 0.028 | 0.012 | 0.003 | 0.003 |
| Ações / valores mobiliários | 0.287 | 0.067 | 0.409 | 1.413 | 0.066 | 0.018 | 0.000 | 0.019 | 0.019 | nan | 0.005 | 0.014 | 0.003 |
| Previdência privada | 0.240 | 0.069 | 0.358 | 0.851 | 0.059 | 0.085 | 0.000 | 0.004 | 0.022 | 0.021 | nan | 0.044 | 0.002 |

![SHAP heatmap](C:/Users/Aluno/Downloads/acessor-investimento/scratch-2026-10-26-396de3/assessor-investimentos/docs/figures/17_shap_importancia.png)

![SHAP Fundos de investimento](C:/Users/Aluno/Downloads/acessor-investimento/scratch-2026-10-26-396de3/assessor-investimentos/docs/figures/18_shap_fundos.png)
