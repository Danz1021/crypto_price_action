#!/bin/zsh
# setup_cron.sh — 自動安裝依賴並設定 Cron Job

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON=$(which python3)
LOG_DIR="$PROJECT_DIR/logs"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " BTC Price Action Bot 安裝設定"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "專案路徑：$PROJECT_DIR"
echo "Python   ：$PYTHON"

# 安裝依賴
echo ""
echo "[1/3] 安裝 Python 依賴..."
$PYTHON -m pip install -r "$PROJECT_DIR/requirements.txt" -q
echo "      ✓ 依賴安裝完成"

# 建立 log 目錄
mkdir -p "$LOG_DIR"

# 測試 Telegram 連線
echo ""
echo "[2/3] 測試 Telegram 連線..."
$PYTHON "$PROJECT_DIR/main.py" --test
echo "      ✓ Telegram 連線成功"

# 設定 Cron
echo ""
echo "[3/3] 設定 Cron Job..."

CRON_15M="*/15 * * * * $PYTHON $PROJECT_DIR/main.py >> $LOG_DIR/signal.log 2>&1"
CRON_DAILY="0 8 * * * $PYTHON $PROJECT_DIR/main.py --daily >> $LOG_DIR/daily.log 2>&1"

# 取得現有 crontab（忽略空 crontab 的 exit 1）
EXISTING=$(crontab -l 2>/dev/null || true)

# 移除舊的同專案設定
CLEANED=$(echo "$EXISTING" | grep -v "$PROJECT_DIR/main.py" || true)

# 寫入新設定
NEW_CRON=$(printf "%s\n%s\n%s\n" "$CLEANED" "$CRON_15M" "$CRON_DAILY")
echo "$NEW_CRON" | crontab -

echo "      ✓ Cron 設定完成"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " 設定完成！Cron Job 如下："
echo ""
echo "  每 15 分鐘 掃描信號："
echo "  $CRON_15M"
echo ""
echo "  每日 08:00 發送完整報告："
echo "  $CRON_DAILY"
echo ""
echo " 查看現有 cron：crontab -l"
echo " 查看即時 log ：tail -f $LOG_DIR/signal.log"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
