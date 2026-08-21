FROM node:22-bookworm-slim AS web-builder

WORKDIR /build/web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM node:22-bookworm-slim AS runtime

ENV API_BASE_URL=http://127.0.0.1:8000 \
    FORTYGUARD_LIVE=0 \
    PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV=/opt/venv
ENV PATH="/opt/venv/bin:${PATH}"

RUN apt-get update \
    && apt-get install --yes --no-install-recommends python3 python3-venv \
    && rm -rf /var/lib/apt/lists/* \
    && python3 -m venv /opt/venv \
    && pip install --no-cache-dir uv==0.11.8

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --active --frozen --no-dev

COPY api/ ./api/
COPY config/ ./config/
COPY data/processed/ ./data/processed/
COPY --from=web-builder /build/web/.next/standalone/ ./web/
COPY --from=web-builder /build/web/.next/static/ ./web/.next/static/
COPY --from=web-builder /build/web/public/ ./web/public/
COPY scripts/start_demo.sh ./scripts/start_demo.sh

RUN chmod +x ./scripts/start_demo.sh

EXPOSE 7860
CMD ["./scripts/start_demo.sh"]
