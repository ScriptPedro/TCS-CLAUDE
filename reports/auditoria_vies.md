# Auditoria de viés

Base auditada: 49.998 clientes com sexo informado. `sexo` não é feature de nenhum modelo (D11): diferenças abaixo vêm de proxies (renda, idade, segmento) ou de padrões históricos de posse.

## Resumo

⚠️ Itens com disparidade relevante entre os sexos:
- CDB / depósito a prazo: razão de impacto 0.74 < 0.8
- Fundos de investimento: razão de impacto 0.63 < 0.8
- Ações / valores mobiliários: razão de impacto 0.66 < 0.8
- Previdência privada: razão de impacto 0.68 < 0.8

- V de Cramér cluster × sexo: **0.169** (cluster × faixa etária: 0.550, para comparação).

## Clusters por sexo (% de cada grupo em cada cluster)

| cluster_nome | H | V |
|---|---|---|
| Adulto só conta | 22.3 | 26.4 |
| Jovem só conta | 45.5 | 29.5 |
| Maduro investidor | 20.3 | 29.8 |
| Maduro investidor (B) | 12.0 | 14.3 |

## Probabilidade média prevista por sexo

`razao_impacto` = menor média ÷ maior média. Abaixo de 0,8 → alerta (regra dos 4/5).

| item | H | V | razao_impacto |
|---|---|---|---|
| Poupança | 0.0 | 0.0 | 1.0 |
| CDB / depósito a prazo | 0.029 | 0.039 | 0.737 |
| Fundos de investimento | 0.012 | 0.019 | 0.628 |
| Ações / valores mobiliários | 0.018 | 0.027 | 0.662 |
| Previdência privada | 0.007 | 0.01 | 0.682 |

## Controlando pela idade: razão de impacto DENTRO de cada faixa etária

Idade média por sexo: H 38,1 anos · V 42,3 anos. Se a razão volta a ficar ≥ 0,8 dentro das faixas, a disparidade geral é explicada pela diferença de idade entre os grupos (proxy), não pelo sexo em si.

| faixa_etaria | Poupança | CDB / depósito a prazo | Fundos de investimento | Ações / valores mobiliários | Previdência privada |
|---|---|---|---|---|---|
| 18-24 | 1.0 | 0.97 | 0.92 | 0.94 | 0.98 |
| 25-34 | 1.0 | 0.8 | 0.72 | 0.8 | 0.89 |
| 35-44 | 1.0 | 0.92 | 0.89 | 0.93 | 0.93 |
| 45-54 | 1.0 | 0.86 | 0.8 | 0.85 | 0.87 |
| 55-64 | 1.0 | 0.94 | 0.75 | 0.78 | 0.99 |
| 65+ | 1.0 | 0.89 | 0.97 | 0.92 | 0.89 |

Disparidades residuais (< 0,8 mesmo dentro da faixa): Fundos de investimento em 25-34: 0.72; Fundos de investimento em 55-64: 0.75; Ações / valores mobiliários em 55-64: 0.78.

## Probabilidade média prevista por faixa etária (transparência)

Idade é critério legítimo de suitability (horizonte de investimento); não gera alerta.

| item | 18-24 | 25-34 | 35-44 | 45-54 | 55-64 | 65+ | razao_impacto |
|---|---|---|---|---|---|---|---|
| Poupança | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 1.0 |
| CDB / depósito a prazo | 0.001 | 0.006 | 0.037 | 0.059 | 0.077 | 0.083 | 0.017 |
| Fundos de investimento | 0.001 | 0.002 | 0.014 | 0.032 | 0.039 | 0.029 | 0.014 |
| Ações / valores mobiliários | 0.002 | 0.004 | 0.026 | 0.047 | 0.048 | 0.034 | 0.032 |
| Previdência privada | 0.001 | 0.001 | 0.007 | 0.019 | 0.025 | 0.009 | 0.037 |

## Como interpretar

- Disparidade **não prova discriminação**: pode refletir diferenças reais de renda entre os grupos na base espanhola de 2016. Também **não prova ausência**: a base reflete as vendas do banco, não a adequação.
- Mitigação disponível: as recomendações finais passam pelo motor de suitability, que usa apenas respostas do próprio usuário (prazo, tolerância, objetivo, reserva). Isso limita o efeito do modelo a ajustes DENTRO das faixas do perfil.
