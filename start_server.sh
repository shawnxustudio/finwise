#!/bin/bash
# 启动 Flask 后端服务

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

PYTHON=/volume1/@appstore/python313/bin/python3
PID_FILE="$SCRIPT_DIR/app.pid"
LOG_FILE="$SCRIPT_DIR/logs/app.log"

mkdir -p "$SCRIPT_DIR/logs"

# 如果已经在运行，不重复启动
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        echo "服务已在运行（PID=$PID）"
        exit 0
    fi
    rm -f "$PID_FILE"
fi

nohup $PYTHON app.py >> "$LOG_FILE" 2>&1 &
echo $! > "$PID_FILE"
echo "$(date '+%Y-%m-%d %H:%M:%S') 服务已启动（PID=$(cat $PID_FILE)）"
