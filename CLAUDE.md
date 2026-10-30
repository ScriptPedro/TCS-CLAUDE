# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

"Assessor de Investimentos Virtual" — an academic Applied AI (BFSI) project. A user fills in a questionnaire and gets a client segment (K-Means), likely products with probabilities and reasons (LightGBM + SHAP), a suggested portfolio by Brazilian asset class, and a plain-language explanation. Models are trained on the Kaggle Santander Product Recommendation dataset (Spanish clients, 2015–2016). Code, identifiers, comments, docs and UI text are in **Portuguese** — keep it that way.

## Commands

Python 3.11 (versions pinned in `requirements.txt`; `numba`/`contourpy` are pinned to avoid numpy 2.x, which breaks shap 0.46). Run everything from the repo root, as modules (`python -m src.X`).

```powershell
py -3.11 -m venv .venv; .venv\Scripts\Activate.ps1; pip install -r requirements.txt
python -m src.download_data                 # Kaggle API; needs ~/.kaggle/kaggle.json + accepted competition rules
python -m src.pipeline                      # full pipeline: prepare → segmentation → recommender → personas → bias audit
python -m src.pipeline --out ensaio --sample-size 5000   # isolated dry run, does not touch data/ models/ reports/
python -m src.prepare_data                  # single stages, in order: prepare_data, segmentation, recommender, personas, bias_audit

pytest                                      # all tests (no Kaggle data or trained models needed)
pytest tests/test_portfolio.py              # one file
pytest tests/test_portfolio.py::test_name   # one test
pytest -k carteira                          # by keyword

streamlit run app/main.py                   # Streamlit UI, http://localhost:8501
uvicorn api.main:app --reload --port 8000   # FastAPI backend for the React front
cd frontend; npm install; npm run dev       # React/Vite front, http://localhost:5173 (proxies /api → :8000)
cd frontend; npm run build                  # type-check (tsc -b) + build; afterwards the API also serves frontend/dist at :8000
```

`ASSESSOR_MODELS_DIR` points the Streamlit app and the API to another folder containing `segmentation.joblib`, `recommender.joblib` and `prep_stats.json`. Streamlit only reloads `app/main.py`, so restart it after changing `src/`.

## Architecture

The core design rule (D4/D16 in `docs/decisoes.md`) is a strict split between **learned models** and **business rules**:

- **ML side** — `src/segmentation.py` (K-Means vs GMM, picks k), `src/recommender.py` (one LightGBM per product item, baselines, metrics, SHAP factors). They train on the processed parquet produced by `src/prepare_data.py` and save `models/*.joblib`.
- **Rules side** — `src/portfolio.py` contains **no ML**: suitability scoring with caps, "protection mode" (expensive card debt / no emergency reserve), min/max allocation ranges per risk profile, and the explanation texts.
- **Bridge** — `src/advisor.py`: `carregar_artefatos()` loads the three artifacts once; `aconselhar(questionario, artefatos)` translates questionnaire answers into dataset-like features (Brazilian income → quintile → equivalent Spanish income by relative position, D3; segment derived by rule), runs cluster + per-item probabilities + SHAP, then calls `portfolio`. In `portfolio.alocar()` the **risk profile defines the range** for each asset class and the **model's affinity only positions within it**.
- Questions without a counterpart in the dataset become business rules, never model features (D4, D22). `sexo` is excluded from all models and not asked in the app; it is used only in `src/bias_audit.py` (D11).

**Two front ends, one logic.** `app/components.py` holds form definitions, answer ranges (faixas), validation and conversion to `Questionario` — testable without Streamlit. `app/main.py` (Streamlit) and `api/main.py` (FastAPI: `/api/saude`, `/api/questionario`, `/api/recomendacao`) both reuse `app.components` + `src.advisor`/`src.portfolio`. The React app in `frontend/src` only renders what the API returns — do not duplicate rules in TypeScript.

**Configuration.** `src/config.py` holds every constant (paths, columns, product → asset-class mapping, seeds `RANDOM_STATE=42`, `SNAPSHOT_DATE`, `SAMPLE_SIZE`, k range, income edges). Other modules must not hardcode "magic" values. `src/pipeline.py` uses a `Paths` object so the whole pipeline can be redirected to another output root (used by `--out` and by tests).

**Tests** never need the real 2.3 GB CSV: `tests/fakes.py` writes a synthetic `train_ver2.csv` reproducing the real file's dirt (padded ages, `NA`, `-999999`, income outliers, duplicates, two months), and `tests/test_recommender._signal_data` builds signal data used to train tiny models into `tmp_path` for `test_app.py` (Streamlit `AppTest`) and `test_api.py` (FastAPI `TestClient`). Tests monkeypatch `config` values (e.g. `K_RANGE`) to stay fast.

## Generated outputs and docs

- Not versioned: `data/raw/`, `data/processed/`, `models/` (only `.gitkeep`). Versioned outputs: `reports/*.md` and `docs/figures/*.png`, regenerated by the pipeline stages.
- `docs/decisoes.md` records every technical decision as D1–D30 (context → decision → discarded alternatives). Code comments reference these IDs; when making a new non-trivial decision, add a new D-entry there. `docs/limitacoes.md` covers limitations/bias/LGPD; `docs/roteiro_apresentacao.md` is the presentation script.
