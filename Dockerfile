# Imagem de produção do Assessor de Investimentos Virtual (D38, D39).
# Um único contêiner: o FastAPI responde em /api e serve o front React compilado.
# Os modelos NÃO entram na imagem: ficam montados em /models (pasta local no Docker,
# bucket no Cloud Run) ou são baixados de ASSESSOR_MODELS_URL ao ligar (Render, D42).
# Os usuários ficam num PostgreSQL à parte, indicado por
# ASSESSOR_DATABASE_URL (D41). Normalmente quem monta e sobe tudo é o Terraform em infra/.
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

# /models é do usuário da API para o download do Render (D42); montagens por cima continuam valendo
RUN useradd --create-home --uid 1000 assessor \
    && mkdir -p /models && chown assessor /models
USER assessor

EXPOSE 8080
# O Cloud Run e o Render definem PORT; "exec" faz o uvicorn receber o sinal de parada direto.
# Antes, baixa os modelos se ASSESSOR_MODELS_URL estiver definida (sem ela, não faz nada).
# Usa ";" e não "&&": se o download falhar, a API sobe assim mesmo e /api/saude mostra o problema.
CMD ["sh", "-c", "python -m api.modelos_remotos; exec uvicorn api.main:app --host 0.0.0.0 --port ${PORT}"]
