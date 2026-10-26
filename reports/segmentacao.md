# Relatório de segmentação

Features: age, renta_log, antiguedad, ind_actividad_cliente, n_liquidez, n_renda_fixa, n_renda_variavel, n_longo_prazo, n_credito + one-hot de segmento.

## Escolha de k

| k | inercia | silhouette | davies_bouldin | calinski_harabasz | gmm_bic |
|---|---|---|---|---|---|
| 2 | 115214.752 | 0.365 | 1.144 | 32858.550 | -964799.327 |
| 3 | 94922.577 | 0.305 | 1.387 | 25285.253 | -1330076.922 |
| 4 | 81940.366 | 0.301 | 1.372 | 22167.452 | -1431926.657 |
| 5 | 72710.155 | 0.284 | 1.327 | 20322.470 | -1457115.926 |
| 6 | 65348.674 | 0.284 | 1.240 | 19215.363 | -1562885.713 |
| 7 | 60376.194 | 0.282 | 1.259 | 18017.497 | -1656314.761 |
| 8 | 56165.743 | 0.273 | 1.237 | 17136.334 | -1634029.696 |
| 9 | 52722.971 | 0.266 | 1.294 | 16381.131 | -1675634.538 |
| 10 | 50081.457 | 0.274 | 1.231 | 15621.690 | -1784617.103 |

Cotovelo em **k=5**. Escolhido **k=4**: maior silhouette na faixa de negócio [4, 8].

![Escolha de k](C:/Users/Aluno/Downloads/acessor-investimento/scratch-2026-10-26-396de3/assessor-investimentos/docs/figures/11_escolha_k.png)

## K-Means × GMM

| modelo | clusters | silhouette | davies_bouldin | menor_cluster_pct |
|---|---|---|---|---|
| K-Means | 4 | 0.301 | 1.372 | 13.246 |
| GMM | 4 | 0.205 | 2.854 | 5.178 |

Concordância entre os dois modelos (ARI): **0.51**.

## Estabilidade (bootstrap 80%, ARI vs. modelo de referência)

[0.993, 0.987, 0.995, 0.991, 0.994] → média **0.992**

## Clusters

- **0 · Jovem só conta** — 36,9% da base · idade média 24 anos · renda mediana 89.444 EUR · 0% investem · 28% ativos · 0,9 produtos em média · predomínio de 'universitario' (99%).
- **1 · Maduro investidor** — 25,4% da base · idade média 56 anos · renda mediana 102.786 EUR · 13% investem · 46% ativos · 1,7 produtos em média · predomínio de 'particulares' (93%).
- **2 · Adulto só conta** — 24,5% da base · idade média 43 anos · renda mediana 98.686 EUR · 6% investem · 54% ativos · 1,3 produtos em média · predomínio de 'particulares' (95%).
- **3 · Maduro investidor (B)** — 13,2% da base · idade média 52 anos · renda mediana 230.312 EUR · 15% investem · 53% ativos · 1,9 produtos em média · predomínio de 'particulares' (83%).

| cluster | tamanho_pct | idade_media | renda_mediana_eur | antiguidade_anos | pct_ativos | n_produtos_medio | pct_investe | pct_liquidez | pct_renda_fixa | pct_renda_variavel | pct_longo_prazo | pct_credito | segmento_predominante | pct_segmento_predominante |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 36.930 | 24.250 | 89444.430 | 2.540 | 27.940 | 0.920 | 0.300 | 80.310 | 0.130 | 0.160 | 0.020 | 0.840 | universitario | 99.280 |
| 1 | 25.360 | 55.800 | 102785.610 | 13.360 | 46.130 | 1.710 | 13.110 | 69.670 | 6.110 | 7.320 | 1.740 | 14.160 | particulares | 93.080 |
| 2 | 24.470 | 42.600 | 98685.750 | 3.530 | 54.090 | 1.300 | 5.840 | 67.270 | 4.040 | 1.990 | 0.310 | 7.640 | particulares | 94.680 |
| 3 | 13.250 | 51.560 | 230311.950 | 11.020 | 53.250 | 1.880 | 15.140 | 72.520 | 6.990 | 8.410 | 2.510 | 16.770 | particulares | 83.380 |

![Tamanhos](C:/Users/Aluno/Downloads/acessor-investimento/scratch-2026-10-26-396de3/assessor-investimentos/docs/figures/12_tamanho_clusters.png)

![Perfil](C:/Users/Aluno/Downloads/acessor-investimento/scratch-2026-10-26-396de3/assessor-investimentos/docs/figures/13_perfil_clusters.png)

![PCA](C:/Users/Aluno/Downloads/acessor-investimento/scratch-2026-10-26-396de3/assessor-investimentos/docs/figures/14_pca_clusters.png)
