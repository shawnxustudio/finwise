#!/bin/bash
# 每日增量同步：爬取论坛新帖 → 更新搜索索引
# 用法：bash sync.sh
#       或由 cron 调用：0 1 * * * /bin/bash /volume1/script/finwise/sync.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

PYTHON=/volume1/@appstore/python313/bin/python3
LOG_DIR="$SCRIPT_DIR/logs"
LOG_FILE="$LOG_DIR/sync_$(date +%Y%m%d).log"

mkdir -p "$LOG_DIR"

echo "========================================" | tee -a "$LOG_FILE"
echo "$(date '+%Y-%m-%d %H:%M:%S') 开始同步" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"

echo "" | tee -a "$LOG_FILE"
echo "--- 第一步：增量爬取 ---" | tee -a "$LOG_FILE"
$PYTHON scrape_full.py --incremental 2>&1 | tee -a "$LOG_FILE"

echo "" | tee -a "$LOG_FILE"
echo "--- 第二步：增量构建索引 ---" | tee -a "$LOG_FILE"
$PYTHON import_data.py --incremental 2>&1 | tee -a "$LOG_FILE"

echo "" | tee -a "$LOG_FILE"
echo "$(date '+%Y-%m-%d %H:%M:%S') 同步完成" | tee -a "$LOG_FILE"

# 只保留最近 30 天的日志
find "$LOG_DIR" -name "sync_*.log" -mtime +30 -delete
