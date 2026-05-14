# ============================================================
# config.py — 全域設定
# 敏感資訊從環境變數讀取（GitHub Actions Secrets）
# ============================================================

import os

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
CHAT_ID        = os.environ.get("CHAT_ID", "")

SYMBOL        = "BTCUSDT"
EXCHANGE_BASE = "https://api.kraken.com"

# 時間框架
TF_DAILY = "1d"
TF_4H    = "4h"
TF_1H    = "1h"
TF_15M   = "15m"
TF_5M    = "5m"

# 擺動點回望 (左右各幾根 K 棒)
SWING_LOOKBACK_DAILY = 5
SWING_LOOKBACK_4H    = 4
SWING_LOOKBACK_1H    = 3
SWING_LOOKBACK_15M   = 3
SWING_LOOKBACK_5M    = 3

# 信號判斷閾值
MIN_RR_RATIO        = 2.0    # 最低風報比 (止盈 ≥ 2R，止損 = 1R)
MAX_SL_PCT          = 0.025  # 止損距離上限 2.5%，超過視為風險過高不做
ATR_PERIOD          = 14
SL_BUFFER_PCT       = 0.003  # SL 在結構失效點外多留 0.3% 緩衝
KEY_LEVEL_TOLERANCE = 0.006  # 0.6%：判斷「是否在關鍵價位附近」
LIQUIDITY_HUNT_BARS = 30     # 往前偵測流動性獵殺的範圍（根）

# 回測參數 (勝率估算)
BACKTEST_BARS         = 300
BACKTEST_FORWARD_BARS = 20
