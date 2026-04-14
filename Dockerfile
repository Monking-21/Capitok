FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

COPY pyproject.toml ./
COPY alembic.ini ./
COPY migrations ./migrations
COPY scripts ./scripts
COPY src ./src

RUN chmod +x ./scripts/*.sh
RUN uv sync --no-dev --no-editable

CMD ["bash", "/app/scripts/start-api.sh", "--prod"]
