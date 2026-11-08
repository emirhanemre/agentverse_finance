# Agent service image (Cloud Run or similar). Prepared, not deployed.
# Build from the repo root:  docker build -f services/agents/Dockerfile -t pubhedge-agents .
FROM python:3.12-slim
RUN pip install --no-cache-dir uv==0.9.*
WORKDIR /srv
COPY pubhedge_core/ pubhedge_core/
COPY data/ data/
COPY fixtures/recorded/ fixtures/recorded/
COPY fixtures/runs/ fixtures/runs/
COPY scripts/backtest.py scripts/gen_synthetic.py scripts/
COPY services/agents/ services/agents/
RUN cd services/agents && uv sync --frozen --no-dev
ENV PUBHEDGE_DB=/tmp/pubhedge.db PORT=8080
# Keys come from the platform's secret manager as env vars; never baked into the image.
CMD ["sh", "-c", "cd services/agents && uv run --no-sync uvicorn pubhedge_svc.app:app --host 0.0.0.0 --port ${PORT}"]
