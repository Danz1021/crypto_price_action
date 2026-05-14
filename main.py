#!/usr/bin/env python3
"""
main.py — 多標的價格行為學分析主程式（9步 SOP + 5時間框架）

使用方式：
  python3 main.py              # 15m 信號掃描（cron 每 15 分鐘）
  python3 main.py --daily      # 日線完整報告（cron 每日早上 08:00）
  python3 main.py --test       # 測試 Telegram 連線
"""

import sys
import logging
import argparse

from config import (
    TELEGRAM_TOKEN, CHAT_ID, EXCHANGE_BASE, SYMBOLS,
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


def analyze_symbol(sym: dict, analyzer: PriceActionAnalyzer, bot: TelegramBot,
                   daily_mode: bool) -> None:
    """對單一標的執行完整分析並視情況發送通知"""
    display      = sym["display"]
    kraken_pair  = sym["kraken_pair"]
    api          = BinanceAPI(EXCHANGE_BASE, kraken_pair, display)

    logger.info("── %s (%s) ──────────────────", display, kraken_pair)

    try:
        daily_df = api.get_klines(TF_DAILY, limit=300)
        tf4h_df  = api.get_klines(TF_4H,   limit=300)
        tf1h_df  = api.get_klines(TF_1H,   limit=300)
        tf15m_df = api.get_klines(TF_15M,  limit=300)
        tf5m_df  = api.get_klines(TF_5M,   limit=150)
        price    = api.get_current_price()
    except Exception as exc:
        logger.error("%s 資料抓取失敗：%s", display, exc)
        return

    logger.info("Price: $%.4f", price)

    analysis = analyzer.run_sop(
        daily_df, tf4h_df, tf1h_df, tf15m_df, tf5m_df,
        current_price=price
    )
    sig = analysis["signal"]
    logger.info("Score: %d/9 | Direction: %s | Strength: %s",
                sig["score"], sig["direction"], sig["strength"])

    if daily_mode:
        bot.send_message(format_full_analysis(analysis, symbol=display))
        return

    # 信號模式
    if sig["risk_too_high"] and sig["score"] >= 5:
        logger.info("Risk too high → skip notice")
        bot.send_message(format_risk_skip(analysis, symbol=display))

    elif sig["has_signal"] and sig["score"] >= 7:
        logger.info("STRONG signal → alert")
        bot.send_message(format_signal_alert(analysis, symbol=display))

    elif sig["has_signal"] and sig["score"] >= 5:
        logger.info("MODERATE signal → summary")
        bot.send_message(format_full_analysis(analysis, symbol=display))

    else:
        logger.info("No signal. Silent.")


def main():
    args     = parse_args()
    analyzer = PriceActionAnalyzer()
    bot      = TelegramBot(TELEGRAM_TOKEN, CHAT_ID)

    # ── 測試模式 ────────────────────────────────
    if args.test:
        ok = bot.test_connection()
        if ok:
            symbols_str = " | ".join(s["display"] for s in SYMBOLS)
            bot.send_message(
                f"✅ *Price Action Bot 9-Step SOP*\n"
                f"連線成功！系統正常運作中。\n"
                f"📌 掃描標的：{symbols_str}\n"
                f"📅 日線報告：每日 08:00\n"
                f"⚡ 信號掃描：每 15 分鐘"
            )
            logger.info("Telegram OK")
        else:
            logger.error("Telegram connection FAILED")
        return

    # ── 所有標的逐一分析 ─────────────────────────
    for sym in SYMBOLS:
        analyze_symbol(sym, analyzer, bot, daily_mode=args.daily)


if __name__ == "__main__":
    main()
