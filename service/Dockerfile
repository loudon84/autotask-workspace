FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY nodeskclaw-task/pyproject.toml ./
RUN uv sync --no-dev

COPY nodeskclaw-task/ .

ENV PYTHONUNBUFFERED=1
EXPOSE 4520

CMD ["/bin/sh", "-c", "uv run alembic upgrade head && uv run uvicorn app.main:app --host 0.0.0.0 --port 4520"]
