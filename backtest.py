"""
backtest.py — 基於歷史資料估算勝率
"""

import pandas as pd
import numpy as np
from patterns import (
    find_swing_points, determine_trend, calc_atr,
    detect_candle_pattern, near_key_level, get_key_levels
)
from config import MIN_RR_RATIO, BACKTEST_BARS, BACKTEST_FORWARD_BARS
ATR_SL_MULT = MIN_RR_RATIO  # backtest 使用相同的 R 倍數


def estimate_win_rate(df: pd.DataFrame,
                      signal_direction: str,
                      swing_lookback: int = 5,
                      atr_period: int = 14) -> dict:
    """
    在 df 最近 BACKTEST_BARS 根 K 棒中，掃描與 signal_direction 相同方向的型態信號。
    勝率 = 信號後 BACKTEST_FORWARD_BARS 根內，價格達到 1R profit target 的比例。

    回傳 {win_rate, sample_size, avg_rr}
    """
    wins   = 0
    losses = 0
    rr_list = []

    start = max(swing_lookback + atr_period, len(df) - BACKTEST_BARS)

    for i in range(start, len(df) - BACKTEST_FORWARD_BARS - 1):
        window = df.iloc[:i + 1].copy()
        atr    = calc_atr(window, atr_period)
        atr_v  = atr.iloc[-1]
        if np.isnan(atr_v) or atr_v == 0:
            continue

        sh, sl = find_swing_points(window, swing_lookback)
        if not sh or not sl:
            continue

        levels   = get_key_levels(sh, sl, n=3)
        price    = window["close"].iloc[-1]
        pattern  = detect_candle_pattern(window)

        if pattern is None:
            continue

        is_bull_pattern = "BULLISH" in pattern
        is_bear_pattern = "BEARISH" in pattern

        if signal_direction == "LONG" and not is_bull_pattern:
            continue
        if signal_direction == "SHORT" and not is_bear_pattern:
            continue

        at_level = near_key_level(price, levels["supports"] + levels["resistances"])
        if not at_level:
            continue

        # 設定 SL / TP
        if signal_direction == "LONG":
            sl_price = price - atr_v * ATR_SL_MULT
            tp_price = price + atr_v * ATR_SL_MULT * 2
        else:
            sl_price = price + atr_v * ATR_SL_MULT
            tp_price = price - atr_v * ATR_SL_MULT * 2

        # 往後看 BACKTEST_FORWARD_BARS 根確認勝負
        future = df.iloc[i + 1 : i + 1 + BACKTEST_FORWARD_BARS]

        if signal_direction == "LONG":
            hit_tp = (future["high"] >= tp_price).any()
            hit_sl = (future["low"]  <= sl_price).any()
        else:
            hit_tp = (future["low"]  <= tp_price).any()
            hit_sl = (future["high"] >= sl_price).any()

        # 先到者決定勝負
        if hit_tp and hit_sl:
            tp_idx = future[future["high"] >= tp_price].index[0] if signal_direction == "LONG" \
                     else future[future["low"] <= tp_price].index[0]
            sl_idx = future[future["low"] <= sl_price].index[0] if signal_direction == "LONG" \
                     else future[future["high"] >= sl_price].index[0]
            won = tp_idx <= sl_idx
        elif hit_tp:
            won = True
        elif hit_sl:
            won = False
        else:
            continue  # 未結束，略過

        if won:
            wins += 1
            rr_list.append(2.0)
        else:
            losses += 1
            rr_list.append(-1.0)

    total = wins + losses
    if total == 0:
        return {"win_rate": 0.5, "sample_size": 0, "avg_rr": 0.0}

    return {
        "win_rate":    wins / total,
        "sample_size": total,
        "avg_rr":      np.mean(rr_list),
    }
