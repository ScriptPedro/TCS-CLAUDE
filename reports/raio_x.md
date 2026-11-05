# Referência brasileira — Raio X do Investidor

Fonte: Raio X do Investidor Brasileiro, 9ª edição (ANBIMA/Datafolha, 2026). Microdados com 5.832 entrevistados, taxas ponderadas pelo peso amostral (`PESOE`). Pergunta usada: P9, *investimentos que utiliza atualmente*.

**Uso no projeto (D36):** complementa o modelo treinado no Santander. Ajusta onde cada classe fica **dentro** da faixa do perfil e alimenta a explicação. Não define o perfil nem as faixas.

No geral, **33,7%** usam ao menos um dos produtos financeiros da carteira (poupança, renda fixa, fundos, ações ou previdência).

## Por faixa de renda individual (mensal)

| Renda | n | Poupança (liquidez) | Renda fixa (CDB, Tesouro...) | Fundos | Ações | Previdência | Algum desses |
|---|---|---|---|---|---|---|---|
| até R$ 1.518 | 2396 | 16,9% | 2,7% | 2,0% | 0,9% | 0,3% | 21,7% |
| de R$ 1.519 a R$ 3.036 | 1686 | 25,3% | 8,4% | 5,3% | 2,1% | 1,9% | 38,2% |
| de R$ 3.037 a R$ 4.554 | 680 | 29,8% | 15,4% | 8,4% | 4,4% | 2,9% | 51,0% |
| de R$ 4.555 a R$ 7.590 | 448 | 30,9% | 22,0% | 12,5% | 4,9% | 5,3% | 56,9% |
| de R$ 7.591 a R$ 15.180 | 176 | 32,1% | 32,2% | 19,7% | 5,8% | 6,5% | 68,7% |
| acima de R$ 15.180 | 62 | 26,5% | 35,3% | 27,5% | 17,5% | 12,6% | 69,3% |

## Por faixa de idade

| Idade | n | Poupança (liquidez) | Renda fixa (CDB, Tesouro...) | Fundos | Ações | Previdência | Algum desses |
|---|---|---|---|---|---|---|---|
| 16 a 24 anos | 967 | 11,0% | 10,8% | 8,6% | 4,3% | 0,4% | 29,5% |
| 25 a 34 anos | 1167 | 18,9% | 12,2% | 7,5% | 3,1% | 1,1% | 36,1% |
| 35 a 44 anos | 1142 | 21,9% | 9,2% | 5,0% | 2,5% | 2,4% | 34,2% |
| 45 a 59 anos | 1397 | 26,7% | 5,8% | 3,6% | 1,5% | 2,5% | 35,0% |
| 60 anos ou mais | 1159 | 26,7% | 5,6% | 2,7% | 0,7% | 1,8% | 32,7% |

## Entrevistados por célula (renda × idade)

| Renda | 16 a 24 anos | 25 a 34 anos | 35 a 44 anos | 45 a 59 anos | 60 anos ou mais |
|---|---|---|---|---|---|
| até R$ 1.518 | 508 | 414 | 411 | 547 | 516 |
| de R$ 1.519 a R$ 3.036 | 277 | 416 | 340 | 386 | 267 |
| de R$ 3.037 a R$ 4.554 | 60 | 165 | 165 | 168 | 122 |
| de R$ 4.555 a R$ 7.590 | 27 | 83 | 110 | 119 | 109 |
| de R$ 7.591 a R$ 15.180 | 9 | 24 | 45 | 56 | 42 |
| acima de R$ 15.180 | 2 | 10 | 16 | 15 | 19 |

Células com menos de 30 entrevistados são aproximadas: a taxa é suavizada em direção à média da faixa de renda (equivalente a 30 entrevistados).

## Mapeamento P9 → classe da carteira

| Resposta da pesquisa | Classe |
|---|---|
| Caderneta de poupança | liquidez |
| Títulos públicos (Tesouro Direto) e títulos privados (CDB, LCI, LCA...) | renda_fixa |
| Fundos de investimento (todos os tipos) | multimercado (analogia) |
| Ações na bolsa | acoes |
| Previdência privada | previdencia |

## Limitações

- Posse **declarada** pelo entrevistado, não registrada pelo banco.
- Mostra o que as pessoas **fazem**, não o que é adequado: por isso nunca define o perfil nem as faixas.
- "Fundos" mistura renda fixa, multimercado, ações e imobiliário.
- A pesquisa não classifica o entrevistado como conservador, moderado ou arrojado.
- Cor, religião, orientação sexual e gênero não são lidos (LGPD).
