# Personas de teste

Esperado = regras determinísticas · Observado = saída do sistema completo.
**Resultado: todas as verificações passaram.**


## Jovem endividado

| Verificação esperada | Resultado |
|---|---|
| perfil conservador | ✅ |
| 5 pontos | ✅ |
| modo proteção ativo | ✅ |
| alertas de cartão e reserva | ✅ |
| liquidez ≥ 60% | ✅ |
| 0% em ações, multimercado e previdência | ✅ |

- **Observado — cluster:** 0 · Jovem só conta
- **Observado — carteira:** Tesouro Selic / CDB liquidez diária 65% · Renda fixa pós-fixada / IPCA+ 35%
- **Observado — produtos sugeridos:** —

## Adulto moderado

| Verificação esperada | Resultado |
|---|---|
| perfil moderado | ✅ |
| 8 pontos | ✅ |
| sem modo proteção | ✅ |
| ações entre 5% e 20% | ✅ |

- **Observado — cluster:** 1 · Maduro investidor
- **Observado — carteira:** Tesouro Selic / CDB liquidez diária 21% · Renda fixa pós-fixada / IPCA+ 41% · Fundos multimercado 11% · Ações / ETFs 20% · Previdência privada 7%
- **Observado — produtos sugeridos:** Ações / valores mobiliários (11%)

## Investidor experiente

| Verificação esperada | Resultado |
|---|---|
| perfil arrojado | ✅ |
| 13 pontos | ✅ |
| sem modo proteção | ✅ |
| ações entre 20% e 45% | ✅ |
| ações > liquidez | ✅ |

- **Observado — cluster:** 3 · Maduro investidor (B)
- **Observado — carteira:** Tesouro Selic / CDB liquidez diária 7% · Renda fixa pós-fixada / IPCA+ 21% · Fundos multimercado 25% · Ações / ETFs 37% · Previdência privada 10%
- **Observado — produtos sugeridos:** —
