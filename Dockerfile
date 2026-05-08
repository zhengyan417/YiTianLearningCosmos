# syntax=docker/dockerfile:1

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

WORKDIR /app

# Build/runtime libraries needed by psycopg2, requests-style HTTPS traffic,
# and a few transitive native dependencies.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        git \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt pyproject.toml README.md /app/
COPY a2a_client /app/a2a_client
COPY cli_client /app/cli_client
COPY code_agent /app/code_agent
COPY core /app/core
COPY file_parse_agent /app/file_parse_agent
COPY rag_agent /app/rag_agent
COPY research_agent /app/research_agent
COPY search_agent /app/search_agent

RUN python -m pip install --upgrade pip setuptools wheel \
    && python -m pip install -r requirements.txt \
    && python -m pip install \
        "langchain-deepseek>=1.0.1" \
        "deepagents>=0.4.4" \
        "google-adk>=1.17.0" \
        "tavily>=1.1.0" \
        "psycopg2>=2.9.11" \
        "requests>=2.32.0"

ENV AGENT_MODULE=code_agent
ENV HOST=0.0.0.0
ENV PORT=10002

CMD ["sh", "-c", "python -m ${AGENT_MODULE} --host ${HOST} --port ${PORT}"]
