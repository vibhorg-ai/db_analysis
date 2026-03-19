FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

ARG HTTPX_REQUEST_TIMEOUT=600
ENV HTTPX_REQUEST_TIMEOUT=${HTTPX_REQUEST_TIMEOUT}

WORKDIR /app

RUN groupadd -r app && useradd -r -g app app

RUN pip install --upgrade pip wheel "setuptools>=65.0.0,<80.9"

COPY requirements-nohash.txt .
RUN pip install \
    --extra-index-url http://telia-nexus.corp.amdocs.com:8081/repository/amaiz-whls/simple \
    --trusted-host telia-nexus.corp.amdocs.com \
    --no-cache-dir \
    -r requirements-nohash.txt

# Ensure setuptools <80.9 so pkg_resources is available (removed in setuptools 80.9+)
RUN pip install --no-cache-dir "setuptools>=65.0.0,<80.9"

COPY backend/ ./backend/
COPY prompts/ ./prompts/
COPY run_api.py .
COPY db_connections.example.yaml ./db_connections.yaml

RUN mkdir -p data memory reports && chown -R app:app /app

USER app
EXPOSE 8004

CMD ["uvicorn", "backend.api.app:app", "--host", "0.0.0.0", "--port", "8004"]