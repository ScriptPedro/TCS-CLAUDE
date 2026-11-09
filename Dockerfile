# Imagem de produção do Assessor de Investimentos Virtual (D38, D39).
# Um único contêiner: o FastAPI responde em /api e serve o front React compilado.
# Os modelos NÃO entram na imagem: ficam montados em /models (pasta local no Docker,
# bucket no Cloud Run). Normalmente quem monta e sobe é o Terraform em infra/.
#
#   docker build -t assessor .
#   docker run -p 8080:8080 -v "$PWD/models:/models:ro" assessor   → http://localhost:8080

# --- 1) Front React -----------------------------------------------------------
FROM node:22-slim AS front
WORKDIR /front
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# --- 2) API Python ------------------------------------------------------------
FROM python:3.11-slim

# libgomp1: o LightGBM precisa do OpenMP em tempo de execução.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    MPLBACKEND=Agg \
    MPLCONFIGDIR=/tmp/matplotlib \
    NUMBA_CACHE_DIR=/tmp/numba \
    ASSESSOR_MODELS_DIR=/models \
    PORT=8080

WORKDIR /app
COPY requirements-deploy.txt .
RUN pip install -r requirements-deploy.txt

COPY src/ src/
COPY app/ app/
COPY api/ api/
COPY --from=front /front/dist frontend/dist

RUN useradd --create-home --uid 1000 assessor
USER assessor

EXPOSE 8080
# O Cloud Run define PORT; "exec" faz o uvicorn receber o sinal de parada direto.
CMD ["sh", "-c", "exec uvicorn api.main:app --host 0.0.0.0 --port ${PORT}"]
