# Limitações, vieses, ética e próximos passos

> Resumo para a banca: o sistema aprende **o que clientes parecidos têm**, não **o que é adequado ter**.
> A adequação vem do motor de suitability (regras explícitas), e o modelo só ajusta pesos dentro dos
> limites que essas regras permitem.

## 1. Limitações dos dados

| Limitação | Impacto | O que fizemos |
|---|---|---|
| **Clientes espanhóis, 2015–2016** | Comportamento, renda e oferta de produtos diferentes do Brasil atual (ex.: depósito espanhol ≠ CDB) | Renda em quintis (D3); mapeamento explícito Santander → classe BR como **analogia** (D25) |
| **Um único banco** | A posse reflete a **política comercial do Santander** (o que foi vendido), não necessariamente o que era bom para o cliente | Modelo limitado a ajustar pesos dentro das faixas de suitability (D25) |
| **Snapshot único (2016-05-28)** | Não modelamos "próximo produto" ao longo do tempo; o MAP@7 não é comparável ao da competição | Avaliação leave-one-out como análogo (D18) |
| **Sem risco, retorno ou preço de ativos** | Não há otimização de carteira (média-variância); as faixas são fixas por perfil | Faixas documentadas e testadas; otimização fica como próximo passo |
| **Renda imputada em ~20% dos clientes** | Ruído na variável mais importante | Imputação por segmento × idade + flag `renta_imputada` (D8) |
| **Sem gasto no cartão, reserva, objetivo, prazo, tolerância** | Essas perguntas não podem ser aprendidas dos dados | Viram **regras de negócio** (D4, D22–D24) |

## 2. Limitações dos modelos

- **Correlação, não causalidade:** "40% dos clientes parecidos têm fundos" não significa que fundos sejam
  adequados para o usuário. Por isso o texto do app diz "clientes com perfil parecido **têm**", e não
  "você **deve** ter".
- **Ponte questionário → features (D16, D27):** o usuário do app não é cliente Santander. A antiguidade
  vem do "tempo de conta em banco", o segmento vem de uma regra, a atividade é fixa em 1 e a renda é
  convertida por quintil com **limites brasileiros aproximados**. Existe diferença entre os dados de
  treino e os do app (*train-serve skew*).
- **O LightGBM pode não superar o baseline:** nos dados sintéticos, ele só venceu quando havia sinal
  individual além do segmento (D20). Se o baseline vencer nos dados reais, isso é um resultado válido e
  deve ser apresentado como tal.
- **Clusters e nomes:** os nomes são gerados por regras e precisam de revisão humana após a execução com
  os dados reais (`CLUSTER_NAME_OVERRIDES`).
- **Validação até aqui:** todo o código foi testado com **dados sintéticos** que reproduzem o formato e
  as "sujeiras" do arquivo real. Os números finais só existem depois de rodar com o `train_ver2.csv`.

## 3. Limitações das regras de negócio

- A pontuação é **inspirada** na Res. CVM 30/2021, mas não é um questionário de suitability homologado.
- O limite de 30% para o cartão é uma **regra prática**, e a reserva é medida em meses de **renda**
  (o questionário não pergunta o custo de vida).
- **Não consideramos:** tributação (IR regressivo, isenção de LCI/LCA), custos e taxas, nível atual da
  Selic/IPCA, valor investido, diversificação dentro de cada classe nem rebalanceamento periódico.

## 4. Vieses identificados

| Viés | Onde aparece | Mitigação |
|---|---|---|
| **Histórico / comercial** | A posse reflete o que o banco ofereceu a cada perfil | Faixas de suitability limitam o efeito do modelo |
| **Proxy de atributo protegido** | `sexo` não é feature, mas renda e segmento podem se correlacionar com ele | `sexo` fora dos modelos (D11) + **auditoria** com regra dos 4/5 (`reports/auditoria_vies.md`) |
| **Etário** | Idade pesa na pontuação e nas features | Uso **legítimo** (horizonte de investimento), auditado só para transparência; o peso da idade na pontuação é baixo (máx. 2 de 14 pontos) |
| **Geográfico / cultural** | Padrões espanhóis aplicados a brasileiros | Declarado no aviso legal do app |
| **Imputação** | Grupos com mais renda faltante recebem a mediana do grupo | Flag de imputação + relatório de qualidade |
| **Sobrevivência** | O snapshot só contém quem ainda era cliente em 2016 | Declarado como limitação |

## 5. Ética e LGPD (Lei 13.709/2018)

- **Minimização:** o app só pergunta o que é usado. **Não pergunta sexo**, nome, CPF nem contato.
- **Sem armazenamento:** as respostas ficam apenas na sessão do navegador (`st.session_state`, em
  memória) e somem ao fechar a página. Os logs registram perfil, cluster e carteira, sem nenhum dado
  identificável.
- **Transparência e explicabilidade (art. 20, revisão de decisões automatizadas):** cada resultado mostra
  a pontuação por pergunta, as faixas, os pesos do modelo e os fatores SHAP de cada produto.
- **Dados de treino:** a base do Kaggle é anonimizada (`ncodpers` é um código, sem PII). As regras da
  competição **não permitem redistribuir** os dados, por isso o `.gitignore` exclui `data/`.
- **Regulação financeira:** recomendação de investimento é atividade regulada (CVM) e exige profissional
  certificado. O app exibe aviso legal permanente e se apresenta como **simulação acadêmica**.
- **Prudência por padrão:** em caso de conflito entre a soma de pontos e uma resposta restritiva, vale a
  mais conservadora (D23). Endividamento ou falta de reserva bloqueiam ativos de risco (D24).

## 6. Próximos passos

1. **Rodar com os dados reais** e revisar os nomes dos clusters, as figuras e os números dos slides.
2. **Substituir os limites de renda** pelos quintis oficiais da PNAD Contínua (IBGE).
3. **Dados brasileiros** (ex.: Open Finance, com consentimento) para eliminar a analogia Espanha → Brasil.
4. **Modelo temporal** ("próximo produto" entre meses), usando os 17 meses do arquivo original.
5. **Otimização de carteira** com retornos e riscos históricos de índices brasileiros (CDI, IMA-B, Ibovespa).
6. **Calibração explícita** das probabilidades (isotônica/Platt) e ajuste de hiperparâmetros (Optuna).
7. **Texto por LLM** (ex.: Claude) a partir do template, sem permissão para alterar números.
8. **Monitoramento** em produção: drift das features, taxa de modo proteção e auditoria de viés periódica.
