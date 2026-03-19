
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Align with backend config HTTPX_REQUEST_TIMEOUT (default 600). Override at build: docker build --build-arg HTTPX_REQUEST_TIMEOUT=900 .
ARG HTTPX_REQUEST_TIMEOUT=600
ENV HTTPX_REQUEST_TIMEOUT=${HTTPX_REQUEST_TIMEOUT}

# For corporate environments with an HTTP proxy, set at build or run time, e.g.:
# ENV http_proxy=http://proxy.example.com:8080
# ENV https_proxy=http://proxy.example.com:8080
# ENV no_proxy="localhost,127.0.0.1,::1"

WORKDIR /app

RUN groupadd -r app && useradd -r -g app app

COPY requirements-prod.txt .
RUN pip install --no-cache-dir -r requirements-prod.txt

COPY backend/ ./backend/
COPY prompts/ ./prompts/
COPY run_api.py .
COPY db_connections.yaml .

RUN mkdir -p data memory reports && chown -R app:app /app

USER app

EXPOSE 8004

CMD ["uvicorn", "backend.api.app:app", "--host", "0.0.0.0", "--port", "8004"]
