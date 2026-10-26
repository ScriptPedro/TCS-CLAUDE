"""Gera um train_ver2.csv sintético com as mesmas colunas e "sujeiras" do original.

Usado nos testes do pipeline completo, para que eles rodem sem baixar os 2,3 GB do Kaggle.
Sujeiras reproduzidas: idade com espaços e "NA", antiguedad "-999999",
renda nula e outliers, segmento nulo, ind_nomina nulo, duplicatas no snapshot
e dois meses no mesmo arquivo.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src import config


def write_fake_raw_csv(path: Path, n_clients: int = 2_500, seed: int = 0) -> Path:
    rng = np.random.default_rng(seed)
    frames = []
    for fecha in ("2016-04-28", config.SNAPSHOT_DATE):
        age = np.array([f"{a:>3}" for a in rng.integers(2, 115, n_clients)], dtype=object)
        age[rng.random(n_clients) < 0.01] = " NA"
        ant = np.array([f"{a:>6}" for a in rng.integers(0, 250, n_clients)], dtype=object)
        ant[rng.random(n_clients) < 0.02] = "-999999"
        renta = rng.lognormal(11.5, 0.6, n_clients)
        renta[rng.random(n_clients) < 0.2] = np.nan
        renta[rng.random(n_clients) < 0.005] = 2.8e7
        df = pd.DataFrame({
            "fecha_dato": fecha,
            "ncodpers": np.arange(1, n_clients + 1),
            "ind_empleado": "N",  # coluna extra do CSV real, descartada na leitura
            "sexo": rng.choice(["H", "V", None], n_clients, p=[0.45, 0.54, 0.01]),
            "age": age,
            "ind_nuevo": rng.choice([0, 1, np.nan], n_clients, p=[0.9, 0.09, 0.01]),
            "antiguedad": ant,
            "segmento": rng.choice(["01 - TOP", "02 - PARTICULARES", "03 - UNIVERSITARIO", None], n_clients, p=[0.05, 0.55, 0.38, 0.02]),
            "renta": renta,
            "ind_actividad_cliente": rng.choice([0, 1], n_clients),
            "canal_entrada": rng.choice(["KHE", "KAT", "KFC", None], n_clients),
        })
        # Posse com algum sinal: renda alta → mais fundos/depósitos
        z = np.nan_to_num((np.log(df["renta"].clip(upper=1e6)) - 11.5) / 0.6)
        for c in config.PRODUCT_COLS:
            p = 0.08 + (0.10 * (z > 0.5) if c in ("ind_fond_fin_ult1", "ind_deco_fin_ult1") else 0)
            df[c] = (rng.random(n_clients) < p).astype(float)
        df["ind_cco_fin_ult1"] = (rng.random(n_clients) < 0.7).astype(float)
        df.loc[rng.random(n_clients) < 0.01, ["ind_nomina_ult1", "ind_nom_pens_ult1"]] = np.nan
        frames.append(df)
    out = pd.concat([*frames, frames[-1].head(3)], ignore_index=True)  # 3 duplicatas no snapshot
    out.to_csv(path, index=False)
    return path
