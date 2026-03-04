# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base

WORKDIR /app
COPY . /app

# 轻量安装：只装 core+server 依赖
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir ".[core,server]"

# 默认启动代码智能体，可通过环境变量切换
ENV AGENT_MODULE=code_agent
ENV HOST=0.0.0.0
ENV PORT=10002

CMD ["sh", "-c", "python -m ${AGENT_MODULE} --host ${HOST} --port ${PORT}"]
