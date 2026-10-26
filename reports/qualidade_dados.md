# Relatório de qualidade dos dados

Gerado por `src/prepare_data.py` · `random_state=42`

## Funil de linhas

| etapa | quantidade |
|---|---|
| Linhas lidas no CSV | 13,647,309 |
| Linhas no snapshot 2016-05-28 | 931,453 |
| Duplicatas de ncodpers removidas | 0 |
| Removidos por idade inválida | 8,362 |
| Amostra final (clientes únicos) | 50,000 |

Shape final: **50,000 linhas × 38 colunas**

## Nulos antes × depois

Antes = snapshot após conversão de tipos; depois = amostra final. Colunas sem nulos foram omitidas.

| coluna | % nulos antes | % nulos depois |
|---|---|---|
| canal_entrada | 0.72 | 0.0 |
| renta | 24.59 | 0.0 |
| segmento | 0.75 | 0.0 |

## Valores inválidos tratados (na amostra)

- antiguedad negativa (código de desconhecido) → imputada: **0**
- renta fora de p1–p99 → winsorizada: **756**

## Estratificação por segmento

| segmento | % população (snapshot) | % amostra |
|---|---|---|
| particulares | 57.89 | 57.89 |
| universitario | 37.53 | 37.53 |
| top | 3.83 | 3.83 |
| desconhecido | 0.75 | 0.75 |

## Distribuições numéricas (amostra final)

renta winsorizada em [25,955; 560,726] EUR (p1–p99).

| variável | count | mean | std | min | 25% | 50% | 75% | max |
|---|---|---|---|---|---|---|---|---|
| age | 50000.0 | 40.4 | 17.0 | 18.0 | 25.0 | 39.0 | 51.0 | 100.0 |
| renta | 50000.0 | 121097.8 | 81964.4 | 25955.1 | 78155.6 | 98685.8 | 134778.5 | 560726.2 |
| antiguedad | 50000.0 | 79.8 | 67.0 | 0.0 | 22.0 | 54.0 | 134.0 | 256.0 |

## Posse de produtos (amostra final)

| produto | % clientes com o produto |
|---|---|
| ind_cco_fin_ult1 | 60.95 |
| ind_recibo_ult1 | 12.24 |
| ind_ctop_fin_ult1 | 10.92 |
| ind_ecue_fin_ult1 | 8.17 |
| ind_cno_fin_ult1 | 7.96 |
| ind_nom_pens_ult1 | 5.79 |
| ind_nomina_ult1 | 5.32 |
| ind_reca_fin_ult1 | 4.96 |
| ind_tjcr_fin_ult1 | 3.71 |
| ind_ctpp_fin_ult1 | 3.64 |
| ind_dela_fin_ult1 | 3.44 |
| ind_valo_fin_ult1 | 2.27 |
| ind_fond_fin_ult1 | 1.59 |
| ind_ctma_fin_ult1 | 0.87 |
| ind_plan_fin_ult1 | 0.86 |
| ind_hip_fin_ult1 | 0.48 |
| ind_viv_fin_ult1 | 0.34 |
| ind_pres_fin_ult1 | 0.22 |
| ind_ctju_fin_ult1 | 0.13 |
| ind_deme_fin_ult1 | 0.09 |
| ind_deco_fin_ult1 | 0.03 |
| ind_cder_fin_ult1 | 0.03 |
| ind_ahor_fin_ult1 | 0.01 |
| ind_aval_fin_ult1 | 0.0 |
