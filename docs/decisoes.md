# Registro de decisões técnicas

Cada decisão segue o formato: contexto → decisão → alternativas descartadas.
Este documento é a "cola" para defender o projeto na banca.

## D1 — Amostra de clientes únicos no snapshot 2016-05-28

- **Contexto:** o arquivo tem ~13,6 M linhas, mas são ~950 mil clientes observados em até 17 meses.
- **Decisão:** filtrar apenas `fecha_dato == 2016-05-28` (1 linha por cliente) e amostrar 50 mil.
- **Descartado:** amostrar linhas do arquivo inteiro — o mesmo cliente apareceria várias vezes,
  inflando clusters e vazando informação entre treino e teste.

## D2 — Leitura em chunks com pandas

- **Decisão:** `pandas.read_csv(chunksize=500_000, usecols=...)`, filtrando cada chunk pela data.
  O pico de memória fica em centenas de MB em vez de ~8 GB.
- **Descartado:** polars lazy — mais rápido, mas adiciona uma segunda API de DataFrame ao projeto
  só para um passo executado uma vez. pandas é suficiente e mais conhecido pela banca.

## D3 — Renda em quantis, não convertida para BRL

- **Contexto:** a renda está em euros, de espanhóis em 2016. Converter para BRL com uma taxa
  não torna o poder de compra comparável (custo de vida, salário mínimo e distribuição diferem).
- **Decisão:** usar a **posição relativa** do cliente (quintis de renda). No app, a renda do usuário
  brasileiro também vira quintil, usando faixas de referência brasileiras.
- **Trade-off:** perde-se a magnitude absoluta, mas o modelo aprende "clientes do topo da distribuição
  tendem a ter fundos", o que é transferível entre países. A taxa `EUR_TO_BRL_RATE` existe no
  `config.py` apenas para exibição ilustrativa.

## D4 — Separação modelo × regras de negócio

- **Decisão:** o modelo usa somente variáveis que existem no dataset. Gasto no cartão, reserva de
  emergência, objetivo, prazo, tolerância a risco e experiência alimentam o motor de suitability
  (`src/portfolio.py`).
- **Motivo:** treinar com variáveis inexistentes exigiria inventar dados (sintéticos), o que a banca
  questionaria como viés introduzido pelos autores.

## D5 — Produtos de crédito não são recomendados

- **Decisão:** `ind_tjcr`, `ind_pres`, `ind_hip`, `ind_viv`, `ind_aval`, `ind_reca` entram apenas como
  sinal de perfil (ex.: ter empréstimo indica endividamento). Um assessor de investimentos não deve
  sugerir crédito.

## D6 — Inclusão de `ind_cno_fin_ult1`

- O dataset tem 24 produtos; a lista original citava 23. `ind_cno_fin_ult1` (conta salário) foi
  adicionado ao grupo **liquidez**.

## D7 — Ordem: filtrar → amostrar → imputar

- **Decisão:** idade inválida e duplicatas são removidas na população inteira do snapshot; só depois
  amostramos 50 mil. Medianas, limites de winsorização e quintis são calculados **na amostra**.
- **Motivo:** filtrar antes garante exatamente 50 mil clientes válidos. Calcular estatísticas na
  amostra mantém o parquet coerente com o `models/prep_stats.json`, que o app reutiliza para tratar a
  entrada do usuário do mesmo jeito.
- **Ressalva (vazamento):** na Etapa 5, a imputação por mediana usa a amostra toda, inclusive o futuro
  conjunto de teste. O efeito é desprezível (mediana de grupo, sem usar o alvo), mas fica registrado.

## D8 — Winsorização p1–p99 antes da imputação de renta

- A renta tem caudas extremas (há valores de dezenas de milhões de euros). Os limites são calculados
  só sobre os valores observados; depois os nulos recebem a mediana de **segmento × faixa etária**,
  com a mediana global como fallback.
- **Descartado:** remover outliers, porque perderia clientes reais de alta renda (segmento TOP).
  Também descartado imputar pela média, que é sensível às caudas.
- A coluna `renta_imputada` (0/1) preserva a informação de que a renda era desconhecida, o que
  permite a auditoria e pode virar feature.

## D9 — antiguedad negativa = ausente

- Valores como `-999999` são códigos de "desconhecido", não meses reais. Eles viram NaN e são imputados
  pela mediana da faixa etária, com a flag `antiguedad_imputada`.

## D10 — Categorias ausentes viram "desconhecido", produtos ausentes viram 0

- Não descartamos clientes por `segmento`/`sexo`/`canal_entrada` nulos: a ausência vira uma categoria
  própria, que também participa da estratificação.
- Produto nulo (ocorre em `ind_nomina`/`ind_nom_pens`) = o cliente não possui o produto.

## D11 — `sexo` não será feature do modelo

- A codificação `H`/`V` é ambígua na documentação do Kaggle, e usar sexo para recomendar
  investimentos é um risco de discriminação. A coluna é mantida apenas para **auditoria de viés**
  (Etapa 8).

## D12 — K-Means como modelo principal, GMM como alternativa

- **K-Means:** centróides interpretáveis ("o cliente típico do cluster"), rápido em 50 mil linhas e
  fácil de explicar para a banca.
- **GMM (Gaussian Mixture):** a alternativa comparada. Permite clusters elípticos e atribuição
  probabilística. Os dois são comparados com as mesmas métricas (silhouette, Davies-Bouldin, tamanho do
  menor cluster) e pela concordância entre eles (ARI).
- **Descartado: autoencoder + K-Means.** Exigiria PyTorch/TensorFlow para reduzir apenas ~13 features.
  O ganho esperado é pequeno com tão poucas dimensões, e a explicabilidade cai.

## D13 — Produtos entram agregados por classe

- Os 24 produtos 0/1 são esparsos (vários com < 1% de posse) e alguns são quase duplicados (conta salário
  × folha de pagamento). Contar por classe (`n_liquidez`, `n_renda_fixa`...) evita contar o mesmo
  comportamento várias vezes e dá clusters nomeáveis.

## D14 — Escala por tipo de variável (StandardScaler × MinMax)

- **Problema encontrado:** com StandardScaler em tudo, uma variável binária rara (previdência) fica a
  muitos desvios-padrão da média para quem a possui, e o K-Means criou um cluster só para ela.
- **Decisão:** contínuas (idade, log renda, antiguidade) usam StandardScaler; binárias e contagens usam
  MinMax 0–1; o segmento usa one-hot.
- **Evidência** (base sintética com 4 personas plantadas):

  | Métrica | StandardScaler em tudo | Escala por tipo |
  |---|---|---|
  | ARI contra as personas reais | 0,89 | 0,997 |
  | Silhouette | 0,31 | 0,49 |
  | ARI K-Means × GMM | 0,38 | 0,98 |

- **Trade-off:** as contínuas variam em cerca de ±3 e as limitadas em [0, 1], então o perfil
  demográfico pesa um pouco mais. Se os clusters reais ignorarem os produtos, aplicamos peso às colunas
  de produto.

## D15 — Escolha de k: silhouette dentro da faixa de negócio [4, 8]

- O cotovelo é subjetivo, e o silhouette sozinho costuma favorecer k=2 (dois segmentos genéricos demais
  para recomendar). A regra é: **maior silhouette entre 4 e 8**. O cotovelo e o BIC do GMM entram no
  gráfico como evidência complementar. É possível forçar outro k com `--k`.
- **Estabilidade:** reamostragens de 80% com ARI ≈ 1 mostram que os clusters não dependem da semente.

## D16 — Ponte entre o questionário e as features (pendente de aprovação)

- O modelo precisa de antiguidade, atividade, segmento e posse de produtos, mas o questionário original
  não pede nada disso. Proposta:
  - **Nova pergunta:** "Quais destes produtos você já tem?" (conta, poupança, CDB/depósito, fundos,
    ações, previdência, cartão, empréstimo). Ela gera os `n_<classe>` e também operacionaliza
    "experiência com investimentos".
  - **Nova pergunta:** "Há quanto tempo você tem conta em banco?" → `antiguedad`.
  - **Regras:** `ind_actividad_cliente = 1` (quem usa o app é ativo); `segmento` derivado por regra
    (universitário se idade < 25 e estudante; top se a renda estiver no quintil mais alto).
  - **Renda:** BRL → quintil brasileiro → mediana da renda espanhola do mesmo quintil (coerente com D3).

## D17 — Formulação: um LightGBM por item, sem o próprio item nas features

- **Alvo:** os 5 itens de investimento do questionário (poupança, CDB/depósito, fundos, ações,
  previdência). Crédito nunca é alvo (D5). Usar a granularidade do questionário, e não os 24 produtos,
  garante que o que o modelo aprende é exatamente o que o app consegue perguntar.
- **Features:** demografia + os OUTROS itens possuídos. O modelo de "fundos" não vê `possui_fundos`,
  porque isso seria vazamento do alvo.
- **Descartados:** multi-label com um único modelo (exigiria mascarar features por saída) e MLP (menos
  interpretável e não supera boosting em dados tabulares desse tamanho).

## D18 — Avaliação honesta para um snapshot único

- A competição original mede MAP@7 de produtos **novos** de um mês para o outro. Com um único snapshot
  (D1), isso não é possível. Usamos três visões:
  1. **AUC por item:** separa quem tem de quem não tem?
  2. **precision@k / MAP@k:** ranqueando os 5 itens. Com 5 itens, MAP@7 = MAP@5. Isso é reportado
     explicitamente, sem fingir equivalência com a competição.
  3. **Leave-one-out (Hit@k, MRR):** esconde um item possuído e mede se ele aparece no topo entre os
     itens "não possuídos". É o análogo mais próximo do uso real do app e da métrica da competição.

## D19 — Early stopping pela log loss, não pela AUC

- **Problema encontrado:** com early stopping monitorando a AUC, o treino parava com 5 a 13 árvores.
  A AUC estabiliza logo, porque só mede ordenação dentro de um item, e as probabilidades ficavam presas
  na taxa média (posse real de 71% num cluster, prevista em 34%).
- **Por que importa:** para ranquear itens **diferentes** para o mesmo cliente, as probabilidades
  precisam estar calibradas entre itens.
- **Decisão:** `eval_metric="binary_logloss"` com `first_metric_only=True`. Resultado: 57 a 86 árvores e
  precision@1 de 0,53 → 0,59.

## D20 — Baseline obrigatório e interpretação do resultado

- Baselines: **popularidade no cluster** (Etapa 4) e **popularidade global**.
- **Teste de sanidade com dois cenários sintéticos:**

  | Cenário | AUC LightGBM | AUC cluster | Hit@1 (LOO) LightGBM | Hit@1 (LOO) cluster |
  |---|---|---|---|---|
  | Posse definida só pela persona (= cluster) | 0,85 | 0,86 | 0,52 | 0,58 |
  | Posse dirigida por renda, idade e co-posse | **0,78** | 0,62 | **0,66** | 0,44 |

- **Leitura:** o LightGBM só vence quando existe sinal **individual** além do segmento. No primeiro
  cenário, o cluster é o preditor ótimo por construção. Com os dados reais, a comparação diz qual dos
  dois mundos é o do Santander. Se o baseline vencer, isso também é um resultado válido para a banca.

## D21 — Versões fixadas de dependências transitivas

- `numba` e `contourpy` recentes forçam numpy 2.x, o que quebra o shap 0.46 (erro no import). Ambos
  foram fixados no `requirements.txt` (`numba==0.60.0`, `contourpy==1.3.0`).

## D22 — Separação física entre regras e ML

- `src/portfolio.py` **não importa nenhum modelo**: só regras de negócio (suitability, saúde financeira,
  faixas, alocação, texto). `src/advisor.py` é a única ponte entre questionário, modelos e regras.
- **Motivo:** dá para auditar e testar as regras sem treinar nada, e trocar o modelo sem mexer nas regras.
  É o mesmo princípio de "regra de negócio ≠ feature" das premissas do projeto.

## D23 — Pontuação de suitability (inspirada na Res. CVM 30/2021)

| Dimensão | Respostas → pontos |
|---|---|
| Prazo | até 1 ano 0 · 1–3 anos 1 · 3–5 anos 2 · > 5 anos 3 |
| Reação a queda de 20% | venderia tudo 0 · venderia parte 1 · manteria 2 · compraria mais 3 |
| Objetivo | reserva 0 · comprar bem / renda extra 1 · aposentadoria 2 · crescer patrimônio 3 |
| Experiência (pelos produtos, D16) | nenhuma 0 · básica 1 · intermediária 2 · avançada 3 |
| Idade | até 34 → 2 · 35–54 → 1 · 55+ → 0 |

- Total de 0 a 14: **0–5 conservador · 6–10 moderado · 11–14 arrojado**.
- **Tetos (a resposta mais restritiva prevalece):** "venderia tudo", prazo de até 1 ano ou objetivo
  reserva → no máximo conservador; nenhuma experiência → no máximo moderado.
  Somar pontos sozinho deixaria um "arrojado que vende tudo na primeira queda".
- **Experiência inferida dos produtos possuídos**, e não autodeclarada, porque é mais objetiva e reutiliza
  a pergunta da D16.

## D24 — Modo proteção: liquidez e reserva antes de qualquer risco

- Ativado se o **gasto no cartão for > 30% da renda** (regra prática de comprometimento de renda) **ou** se
  a **reserva for < 6 meses de renda**.
- Efeito: perfil efetivo conservador, liquidez ≥ 60% e **multimercado, ações e previdência zerados**. O
  modelo também fica proibido de sugerir esses produtos (a regra prevalece sobre a probabilidade).
- A reserva é medida em meses de **renda** porque o questionário não pergunta o custo de vida. Isso é
  conservador: a reserva-alvo fica maior.

## D25 — Perfil define a faixa; o modelo define a posição dentro dela

- Cada perfil tem uma faixa (mín, máx) por classe brasileira. Cada classe começa no mínimo, e o espaço
  livre é repartido proporcionalmente à afinidade do modelo (P(item) mapeado para a classe), sem
  ultrapassar o máximo ("water-filling"). O arredondamento é pelo maior resto, com soma sempre 100.
- **Garantia testada:** para qualquer afinidade (60 combinações aleatórias × 3 perfis), a soma é 100 e
  todas as classes ficam dentro da faixa.
- Classes opcionais com menos de 3% são zeradas e redistribuídas, porque 1% em previdência não tem efeito
  prático.
- **Mapeamento explícito Santander → Brasil** (analogia, não equivalência): poupança → liquidez;
  depósitos → renda fixa pós/IPCA+; fundos → multimercado; valores/derivativos → ações/ETFs;
  plano de pensões → previdência.

## D26 — Explicação por template, não por LLM

- O texto é gerado por template determinístico: mesma entrada, mesmo texto, sem risco de o LLM
  "inventar" uma recomendação. Os motivos de cada produto vêm do SHAP (Etapa 5).
- **Erro encontrado e corrigido:** o texto dizia "pesou a favor: Já tem CDB" para quem NÃO tinha CDB
  (o SHAP indicava que a ausência pesava). O rótulo agora depende do valor da feature: "Já tem…" ou
  "Ainda não tem…".
- Itens com P < 10% não são sugeridos. Sem itens elegíveis, o texto orienta o rebalanceamento.
- Um LLM (ex.: Claude) poderia reescrever o texto em tom mais natural, recebendo os números como entrada
  e sem poder alterá-los. Fica como próximo passo.

## D27 — Ponte de renda BRL → EUR (pendente de dado oficial)

- Renda mensal BRL → quintil brasileiro → média geométrica dos limites do mesmo quintil na base
  espanhola (coerente com D3).
- Os limites brasileiros no `config.py` (R$ 1.500 / 2.500 / 4.000 / 7.000) são **aproximações** e devem
  ser substituídos pelos quintis oficiais da PNAD Contínua (IBGE) antes da apresentação.

## D28 — App fino: layout no `main.py`, lógica testável fora dele

- `app/main.py` cuida só de layout e navegação. `app/components.py` (validação do formulário, avisos,
  gráfico) não importa Streamlit e é testado com pytest. Toda a decisão fica em `src/advisor.py`.
- O fluxo completo é testado com `streamlit.testing.AppTest`, que preenche o formulário, envia e confere
  as métricas, o modo proteção, as entradas inválidas, o botão "refazer" e a ausência de modelos.

## D29 — Navegação sem `st.rerun()`

- O formulário fica num `st.empty()`. Ao enviar com sucesso, ele é esvaziado e o resultado é desenhado
  na **mesma** execução. O botão "Refazer" usa `on_click=` (callback), que roda antes da próxima execução.
- **Motivo:** com `st.rerun()`, o script roda duas vezes por clique, e o AppTest mantinha widgets
  "fantasma" do formulário, o que fez o teste de "refazer" falhar. O padrão com placeholder e callback é
  mais simples e mais rápido.

## D30 — Ajustes encontrados testando no navegador

- **Nome do segmento truncado:** em 640px, "Adulto só conta" virava "Adulto só c…" dentro do
  `st.metric`, que não quebra linha. O segmento agora fica numa linha de texto própria.
- **Números no padrão americano:** "R$ 30,000" e "0.0 meses". Criados `fmt_brl`/`fmt_num` em
  `src/utils.py`, usados nos alertas e nas descrições dos clusters.
- **Verificado em 375px (celular):** sem rolagem horizontal e sem texto truncado. O Streamlit empilha
  as colunas.
- **Gráfico de rosca** (pedido do projeto): no máximo 5 fatias, cor fixa por classe (paleta validada para
  daltonismo), rótulos com % e legenda. Classes com 0% são omitidas.

## D31 — Itens raríssimos ficam sem modelo (encontrado nos dados reais)

- **Problema:** na base real, a poupança (`ind_ahor`) tem cerca de 4 positivos em 50 mil clientes. No
  sorteio interno de validação, todos caíram na validação, e o LightGBM quebrou com
  `y contains previously unseen labels: [1]`.
- **Decisão:** a validação interna passa a ser estratificada pelo alvo. Itens com menos de
  `MIN_POSITIVES_TO_TRAIN` (50) positivos no treino não recebem modelo: a probabilidade é a taxa média e
  não há fatores SHAP. O relatório lista os itens pulados.
- **Por que não forçar o treino:** com 2 a 4 exemplos positivos, qualquer modelo só decoraria ruído.

## D32 — Auditoria de viés controlada por idade (resultado real)

- Na base real houve 4 alertas por sexo (razões de 0,63 a 0,74). O grupo `H` é cerca de 4 anos mais
  jovem (38,1 contra 42,3 anos) e está muito mais no cluster jovem.
- **Dentro de cada faixa etária**, a maioria das razões volta a ficar ≥ 0,8: a disparidade é
  majoritariamente um efeito de **idade como proxy**. Restam 3 casos residuais (fundos em 25–34 e
  55–64; ações em 55–64), que devem ser apresentados como limitação.

## D33 — Cinco perguntas de refinamento, cada uma ligada a uma regra

Princípio: **nenhuma pergunta é só informativa** (minimização da LGPD). Toda pergunta nova muda uma regra:

| Pergunta | Regra |
|---|---|
| Quantas pessoas dependem da sua renda? | 3 ou mais → perfil no máximo **moderado** (menos capacidade de absorver perdas) |
| Como é a sua renda? | variável ou sem renda fixa → reserva-alvo de **12 meses** em vez de 6 |
| Paga juros de rotativo ou de cheque especial? | sim → **modo proteção**, mesmo com reserva completa |
| Como avalia seu conhecimento? | experiência considerada = o **menor** nível entre o declarado e o inferido dos produtos |
| Pode precisar do dinheiro antes do prazo? | talvez → +10, sim → +20 pontos no mínimo de liquidez (a renda fixa cede se os mínimos passarem de 100%) |

- A pontuação de 0 a 14 e as faixas de perfil **não mudaram**: as perguntas novas atuam como tetos e
  ajustes. Assim as personas, os testes e os slides continuam válidos.
- Testado: as faixas continuam viáveis em todas as combinações (pior caso: modo proteção + 20 pontos).

## D34 — Faixas no lugar de valores digitados

- Renda, gasto no cartão, reserva e tempo de conta passaram a ser escolhidos por **faixas** (controle
  deslizante). O cartão é perguntado como **% da renda** e a reserva como **meses de renda**, que é como
  as regras raciocinam.
- Cada faixa vira um valor representativo (ex.: "R$ 4.000 a R$ 7.000" → R$ 5.500).
- **As bordas das faixas coincidem com os limites das regras** (30% no cartão, 6 e 12 meses de
  reserva), então a faixa escolhida decide a regra sem ambiguidade. Há um teste que verifica isso.
- O questionário virou um assistente em 4 etapas (Sobre você · Suas finanças · Seus objetivos · Você e o
  risco), com barra de progresso, "Voltar" que preserva as respostas e "Ajustar respostas" na tela final.

## D35 — Carteira explicada em linguagem simples

- **Em resumo:** três frases (quem você é, qual a prioridade, o que fazer com o dinheiro).
- **Um cartão por classe:** % e "R$ X de cada R$ 1.000", o que é, para que serve, risco, prazo de resgate
  e **por que essa %** (faixa do perfil + posição dentro dela pela afinidade do modelo).
- **Próximos passos:** ações concretas e ordenadas (quitar dívida, completar reserva, rebalancear).
- **Risco da carteira:** média ponderada (1–4) com rótulo. Os limites foram calibrados para que o rótulo
  **nunca fique acima do perfil**: na primeira versão, uma carteira conservadora aparecia com risco
  "moderado". Há um teste com 300 carteiras aleatórias por perfil.
- **Bug encontrado no navegador:** "R$ 640 de cada R$ 1.000" virava fórmula LaTeX ("R640decadaR"),
  porque o Streamlit interpreta o texto entre dois `$` como matemática. Todos os textos dinâmicos passam
  por `md()`, que escapa o `$`.
