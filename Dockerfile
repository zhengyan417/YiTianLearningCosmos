# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base

WORKDIR /app
COPY . /app

# psycopg2 需要 libpq-dev 和 gcc 进行编译
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
  && rm -rf /var/lib/apt/lists/*

# 安装 core+server 依赖（含所有 [project.dependencies] 主依赖）
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir ".[core,server]"

# 默认启动代码智能体，可通过环境变量切换
ENV AGENT_MODULE=code_agent
ENV HOST=0.0.0.0
ENV PORT=10002

CMD ["sh", "-c", "python -m ${AGENT_MODULE} --host ${HOST} --port ${PORT}"]
