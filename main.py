#!/usr/bin/env python3
"""
main.py — BTC 價格行為學分析主程式（9步 SOP + 5時間框架）

使用方式：
  python3 main.py              # 15m 信號掃描（cron 每 15 分鐘）
  python3 main.py --daily      # 日線完整報告（cron 每日早上 08:00）
  python3 main.py --test       # 測試 Telegram 連線

Cron：
  */15 * * * * /usr/bin/python3 /Users/dan.zheng/btc-price-action/main.py >> /Users/dan.zheng/btc-price-action/logs/signal.log 2>&1
  0 8  * * * /usr/bin/python3 /Users/dan.zheng/btc-price-action/main.py --daily >> /Users/dan.zheng/btc-price-action/logs/daily.log 2>&1
"""

import sys
import logging
import argparse

from config import (
    TELEGRAM_TOKEN, CHAT_ID, SYMBOL, EXCHANGE_BASE,
    TF_DAILY, TF_4H, TF_1H, TF_15M, TF_5M,
)
from binance_api  import BinanceAPI
from price_action import PriceActionAnalyzer
from telegram_bot import TelegramBot
from formatter    import format_full_analysis, format_signal_alert, format_risk_skip

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--daily", action="store_true", help="發送每日完整分析")
    p.add_argument("--test",  action="store_true", help="測試 Telegram 連線")
    return p.parse_args()


def main():
    args = parse_args()
    api      = BinanceAPI(EXCHANGE_BASE, SYMBOL)
    analyzer = PriceActionAnalyzer()
    bot      = TelegramBot(TELEGRAM_TOKEN, CHAT_ID)

    # ── 測試模式 ────────────────────────────────
    if args.test:
        ok = bot.test_connection()
        if ok:
            bot.send_message(
                "✅ *BTC Price Action Bot 9-Step SOP*\n"
                "連線成功！系統正常運作中。\n"
                "📅 日線報告：每日 08:00\n"
                "⚡ 信號掃描：每 15 分鐘"
            )
            logger.info("Telegram OK")
        else:
            logger.error("Telegram connection FAILED")
        return

    # ── 抓取資料（5個時間框架）───────────────────
    logger.info("Fetching BTCUSDT data (5 timeframes)…")
    daily_df = api.get_klines(TF_DAILY, limit=300)
    tf4h_df  = api.get_klines(TF_4H,   limit=300)
    tf1h_df  = api.get_klines(TF_1H,   limit=300)
    tf15m_df = api.get_klines(TF_15M,  limit=300)
    tf5m_df  = api.get_klines(TF_5M,   limit=150)
    price    = api.get_current_price()
    logger.info("Current price: $%.2f", price)

    # ── 執行 9步 SOP ────────────────────────────
    analysis = analyzer.run_sop(
        daily_df, tf4h_df, tf1h_df, tf15m_df, tf5m_df,
        current_price=price
    )
    sig = analysis["signal"]
    logger.info("Score: %d/9 | Direction: %s | Strength: %s",
                sig["score"], sig["direction"], sig["strength"])

    # ── 日線報告模式 ─────────────────────────────
    if args.daily:
        bot.send_message(format_full_analysis(analysis))
        logger.info("Daily report sent.")
        return

    # ── 即時信號掃描 ─────────────────────────────
    if sig["risk_too_high"] and sig["score"] >= 5:
        logger.info("Risk too high (SL %.1f%%) → sending skip notice", sig["sl_pct"])
        bot.send_message(format_risk_skip(analysis))

    elif sig["has_signal"] and sig["score"] >= 7:
        logger.info("STRONG signal → sending alert")
        bot.send_message(format_signal_alert(analysis))

    elif sig["has_signal"] and sig["score"] >= 5:
        logger.info("MODERATE signal → sending summary")
        bot.send_message(format_full_analysis(analysis))

    else:
        logger.info("No signal (score=%d). Silent.", sig["score"])


if __name__ == "__main__":
    main()
