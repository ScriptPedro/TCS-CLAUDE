# Roteiro de apresentação (13 min + perguntas)

Mensagem central, para repetir no início e no fim:
**"A IA descobre com quem você se parece; as regras garantem que a recomendação seja adequada para você."**

## Estrutura

| # | Slide | Tempo | Conteúdo | Evidência |
|---|---|---|---|---|
| 1 | Problema | 0:45 | Quem tem pouco patrimônio não tem acesso a assessoria. Proposta: assessor virtual explicável | — |
| 2 | Solução em 1 imagem | 1:00 | Questionário → [IA: segmento + afinidade] + [Regras: suitability] → carteira + explicação | Diagrama de arquitetura (README) |
| 3 | Dados e premissas | 1:15 | Santander/Kaggle: 13,6 M linhas → 50 mil clientes únicos do último mês. O que o dataset **não** tem vira regra | Funil de `qualidade_dados.md`; D1, D4 |
| 4 | Preparação | 0:45 | Nulos antes × depois, winsorização, estratificação preservada | Tabelas de `qualidade_dados.md` |
| 5 | EDA: 3 achados | 1:15 | (a) maioria só tem conta; (b) investir cresce com renda/idade; (c) produtos formam "pacotes" | Figuras 03, 06, 10 |
| 6 | Segmentação | 1:30 | Escolha de k (regra explícita), perfil dos clusters, estabilidade (ARI ≈ 1), K-Means × GMM | Figuras 11, 13; D15 |
| 7 | Achado metodológico | 0:45 | StandardScaler numa variável binária rara criou um cluster "só previdência". Correção: escala por tipo | Tabela antes/depois da D14 |
| 8 | Recomendação | 1:30 | LightGBM por item sem vazamento; comparação com baselines; leave-one-out | Figuras 15, 16; D17, D18 |
| 9 | Explicabilidade | 0:45 | SHAP: o que pesa em cada produto e em que direção | Figuras 17, 18 |
| 10 | Suitability e carteira | 1:15 | Pontuação + tetos, modo proteção, "perfil define a faixa, modelo define a posição" | Tabela da D23; D24, D25 |
| 11 | **Demo ao vivo** | 1:30 | Jovem endividado (escudo, 0% de risco) → investidor experiente (arrojado) | App ou vídeo de reserva |
| 12 | Validação | 0:30 | ~200 testes automatizados, 3 personas com saídas esperadas, auditoria de viés | `personas.md`, `auditoria_vies.md` |
| 13 | Limitações e ética | 0:45 | Dados espanhóis de 2016, posse ≠ adequação, LGPD, sexo fora do modelo e auditado | `limitacoes.md` |
| 14 | Conclusão e próximos passos | 0:30 | Repetir a mensagem central; dados brasileiros, modelo temporal, otimização | — |

**Total: ~13 min.** Ensaie com cronômetro. Se faltar tempo, encurte os slides 4 e 9.

## Divisão sugerida entre integrantes

- **A:** slides 1–5 (problema, dados, EDA)
- **B:** slides 6–9 (modelos de IA)
- **C:** slides 10–14 (regras, demo, validação, ética)

## Checklist da véspera

- [ ] Pipeline rodado com os dados **reais** (`python -m src.pipeline`) e figuras atualizadas nos slides
- [ ] Nomes dos clusters revisados (`CLUSTER_NAME_OVERRIDES` no `config.py`)
- [ ] Quintis de renda da PNAD/IBGE no `config.py` (D27)
- [ ] `pytest` passando
- [ ] App testado no notebook da apresentação, **sem internet**
- [ ] Vídeo de 90 s da demo gravado (plano B)
- [ ] Respostas das personas anotadas para preencher rápido na demo

## Perguntas prováveis da banca (e onde está a resposta)

| Pergunta | Resposta curta | Referência |
|---|---|---|
| Por que não amostrar linhas do arquivo inteiro? | O mesmo cliente apareceria até 17 vezes: clusters inflados e vazamento entre treino e teste | D1 |
| Dados espanhóis servem para brasileiros? | Parcialmente. Usamos a **posição relativa** de renda (quintis) e mapeamos produtos por analogia. É a principal limitação | D3, D25, limitações §1 |
| Onde está a IA, se a carteira vem de regras? | Em três lugares: segmentação (K-Means), afinidade por produto (LightGBM) e explicação (SHAP). As regras garantem adequação, e a IA personaliza dentro delas | D25 |
| Por que K-Means e não outro algoritmo? | Centróides interpretáveis e escaláveis. Comparamos com GMM pelas mesmas métricas e pela concordância (ARI) | D12 |
| Como escolheram k? | Maior silhouette dentro da faixa de negócio [4, 8], com cotovelo e BIC como evidência complementar | D15 |
| Como sabem que os clusters são reais? | Estabilidade em reamostragens (ARI ≈ 1) e concordância com GMM. Nos dados sintéticos, recuperamos as personas plantadas (ARI 0,997) | D14, D15 |
| O modelo não "cola" ao ver o próprio produto? | Não: cada modelo exclui a flag do próprio item. O heatmap SHAP mostra "—" nessas células | D17, figura 17 |
| Por que não usaram acurácia? | Posse desbalanceada: prever "não tem" daria acurácia alta e inútil. Usamos AUC, MAP@k e leave-one-out | D18 |
| E se o baseline ganhar do LightGBM? | É um resultado: indica que o segmento já explica a posse. Mostramos os dois cenários sintéticos que explicam quando cada um vence | D20 |
| Por que early stopping pela log loss? | A AUC estabilizava cedo e deixava as probabilidades descalibradas, o que atrapalha comparar itens diferentes | D19 |
| O sistema discrimina por sexo? | `sexo` não entra em nenhum modelo, e o app não o pergunta. Mesmo assim auditamos proxies com a regra dos 4/5 | D11, `auditoria_vies.md` |
| E a LGPD? | Minimização (sem PII), sem armazenamento, explicação de cada decisão (art. 20) e aviso legal | limitações §5 |
| Por que template e não ChatGPT/LLM no texto? | Determinístico e auditável: o texto nunca contradiz os números. LLM é próximo passo, só para o tom | D26 |
| O que fariam com mais tempo? | Dados brasileiros, modelo temporal com os 17 meses, otimização média-variância, calibração | limitações §6 |
