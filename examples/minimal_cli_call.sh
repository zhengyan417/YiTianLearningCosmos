#!/usr/bin/env bash
# 示例：启动研究智能体后，用 CLI 发送一次请求

set -euo pipefail

# 启动研究智能体（需提前配置 .env）
python -m research_agent --host localhost --port 10005 &
AGENT_PID=$!
sleep 3

echo "call via CLI:"
cd cli_client
python __main__.py --agent http://localhost:10005 <<'EOF'
:q
EOF

kill $AGENT_PID
