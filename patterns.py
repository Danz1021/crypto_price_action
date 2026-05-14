"""
patterns.py — 價格行為學核心技術偵測模組

包含：ATR、擺動點、趨勢、BOS/MSB、FVG、Order Block、
      供需區、流動性獵殺、K 線型態、關鍵價位工具
"""

import numpy as np
import pandas as pd
from typing import Optional


# ─────────────────────────────────────────────
# ATR
# ─────────────────────────────────────────────

def calc_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    h_l  = df["high"] - df["low"]
    h_pc = (df["high"] - df["close"].shift(1)).abs()
    l_pc = (df["low"]  - df["close"].shift(1)).abs()
    tr   = pd.concat([h_l, h_pc, l_pc], axis=1).max(axis=1)
    return tr.ewm(span=period, adjust=False).mean()


# ─────────────────────────────────────────────
# 擺動高低點
# ─────────────────────────────────────────────

def find_swing_points(df: pd.DataFrame, lookback: int = 5) -> tuple[list, list]:
    """回傳 (swing_highs, swing_lows)，每個元素為 {index, price, time}"""
    highs, lows = [], []
    n = len(df)

    for i in range(lookback, n - lookback):
        window_h = df["high"].iloc[i - lookback : i + lookback + 1]
        window_l = df["low"].iloc[i  - lookback : i + lookback + 1]
        if df["high"].iloc[i] == window_h.max():
            highs.append({"index": i, "price": df["high"].iloc[i], "time": df.index[i]})
        if df["low"].iloc[i] == window_l.min():
            lows.append({"index": i, "price": df["low"].iloc[i], "time": df.index[i]})

    return highs, lows


# ─────────────────────────────────────────────
# 趨勢結構
# ─────────────────────────────────────────────

def determine_trend(swing_highs: list, swing_lows: list) -> str:
    if len(swing_highs) < 2 or len(swing_lows) < 2:
        return "RANGING"
    sh = [s["price"] for s in swing_highs[-2:]]
    sl = [s["price"] for s in swing_lows[-2:]]
    if sh[1] > sh[0] and sl[1] > sl[0]:
        return "UPTREND"
    if sh[1] < sh[0] and sl[1] < sl[0]:
        return "DOWNTREND"
    return "RANGING"


# ─────────────────────────────────────────────
# BOS / MSB
# ─────────────────────────────────────────────

def detect_bos(df: pd.DataFrame, swing_highs: list, swing_lows: list, trend: str) -> Optional[dict]:
    if not swing_highs or not swing_lows:
        return None
    last_close = df["close"].iloc[-1]

    if trend == "UPTREND":
        sh_price = swing_highs[-1]["price"]
        sl_price = swing_lows[-1]["price"]
        if last_close > sh_price:
            return {"type": "BOS_BULLISH", "level": sh_price, "desc": "多頭結構突破（BOS）趨勢延續"}
        if last_close < sl_price:
            return {"type": "MSB_BEARISH", "level": sl_price, "desc": "市場結構反轉（MSB）多頭失效警告"}
    elif trend == "DOWNTREND":
        sl_price = swing_lows[-1]["price"]
        sh_price = swing_highs[-1]["price"]
        if last_close < sl_price:
            return {"type": "BOS_BEARISH", "level": sl_price, "desc": "空頭結構突破（BOS）趨勢延續"}
        if last_close > sh_price:
            return {"type": "MSB_BULLISH", "level": sh_price, "desc": "市場結構反轉（MSB）空頭失效警告"}
    return None


# ─────────────────────────────────────────────
# 供需區（Supply / Demand Zone）
# ─────────────────────────────────────────────

def find_supply_demand_zones(df: pd.DataFrame, atr: pd.Series,
                              lookback: int = 80, min_move_atr: float = 2.0) -> list:
    """
    Demand Zone：強力上漲前的整理區（需求區，多方力量集中地）
    Supply Zone ：強力下跌前的整理區（供給區，空方力量集中地）
    品質 HIGH = 脫離速度 > 3×ATR，MEDIUM = 2~3×ATR
    """
    zones = []
    atr_val = atr.iloc[-1] if not np.isnan(atr.iloc[-1]) else 1000

    start = max(4, len(df) - lookback)

    for i in range(start, len(df) - 4):
        atr_i = atr.iloc[i] if not np.isnan(atr.iloc[i]) else atr_val

        # ── Demand Zone ──────────────────────────
        # 找整理後的強力上漲（後 3 根收高且總漲幅 > min_move_atr × ATR）
        up_move = df["close"].iloc[i + 3] - df["close"].iloc[i]
        if up_move > atr_i * min_move_atr:
            all_bull = all(df["close"].iloc[i + j] > df["open"].iloc[i + j]
                           for j in range(1, 4))
            if all_bull:
                zone_high = df["high"].iloc[max(0, i - 1) : i + 1].max()
                zone_low  = df["low"].iloc[max(0, i - 1)  : i + 1].min()
                quality   = "HIGH" if up_move > atr_i * 3 else "MEDIUM"
                zones.append({
                    "type":    "DEMAND_ZONE",
                    "top":     zone_high,
                    "bottom":  zone_low,
                    "quality": quality,
                    "time":    df.index[i],
                })

        # ── Supply Zone ──────────────────────────
        down_move = df["close"].iloc[i] - df["close"].iloc[i + 3]
        if down_move > atr_i * min_move_atr:
            all_bear = all(df["close"].iloc[i + j] < df["open"].iloc[i + j]
                           for j in range(1, 4))
            if all_bear:
                zone_high = df["high"].iloc[max(0, i - 1) : i + 1].max()
                zone_low  = df["low"].iloc[max(0, i - 1)  : i + 1].min()
                quality   = "HIGH" if down_move > atr_i * 3 else "MEDIUM"
                zones.append({
                    "type":    "SUPPLY_ZONE",
                    "top":     zone_high,
                    "bottom":  zone_low,
                    "quality": quality,
                    "time":    df.index[i],
                })

    # 只保留最近 6 個，去除重疊（價格相差 < 0.5%）
    zones = _deduplicate_zones(zones[-6:])
    return zones


def _deduplicate_zones(zones: list) -> list:
    result = []
    for z in zones:
        mid = (z["top"] + z["bottom"]) / 2
        if not any(abs(mid - (r["top"] + r["bottom"]) / 2) / mid < 0.005
                   for r in result):
            result.append(z)
    return result


def nearest_zone_above(price: float, zones: list) -> Optional[dict]:
    """取最近的在現價上方的供給區"""
    candidates = [z for z in zones if z["bottom"] > price]
    return min(candidates, key=lambda z: z["bottom"], default=None)


def nearest_zone_below(price: float, zones: list) -> Optional[dict]:
    """取最近的在現價下方的需求區"""
    candidates = [z for z in zones if z["top"] < price]
    return max(candidates, key=lambda z: z["top"], default=None)


# ─────────────────────────────────────────────
# 流動性獵殺偵測（假突破）
# ─────────────────────────────────────────────

def detect_liquidity_hunt(df: pd.DataFrame,
                           swing_highs: list,
                           swing_lows: list,
                           lookback: int = 30) -> dict:
    """
    偵測近期流動性獵殺（Liquidity Sweep / Fake Breakout）。

    多方獵殺 (BULLISH_SWEEP)：
      價格跌破支撐後迅速反轉收回 → 空頭止損被掃、反轉做多機會。
    空方獵殺 (BEARISH_SWEEP)：
      價格突破壓力後迅速反轉收回 → 多頭止損被掃、反轉做空機會。

    回傳 {detected: bool, type, level, desc, candles_ago}
    """
    recent = df.iloc[-lookback:]
    best_hunt = None
    best_recency = lookback + 1

    # 收集關鍵價位
    sh_prices = [s["price"] for s in swing_highs[-6:]]
    sl_prices = [s["price"] for s in swing_lows[-6:]]

    for i in range(1, len(recent)):
        c = recent.iloc[i]
        total_range = c["high"] - c["low"]
        if total_range == 0:
            continue
        candles_ago = len(recent) - 1 - i

        # 多方獵殺：跌破支撐後收回（下影線突破）
        for lvl in sl_prices:
            if (c["low"] < lvl and
                c["close"] > lvl and
                (c["close"] - c["low"]) / total_range > 0.55):
                if candles_ago < best_recency:
                    best_recency = candles_ago
                    best_hunt = {
                        "detected":    True,
                        "type":        "BULLISH_SWEEP",
                        "level":       lvl,
                        "candles_ago": candles_ago,
                        "desc":        f"多方流動性獵殺：跌破支撐 ${lvl:,.0f} 後反轉收回（空頭止損被掃）",
                    }

        # 空方獵殺：突破壓力後收回（上影線突破）
        for lvl in sh_prices:
            if (c["high"] > lvl and
                c["close"] < lvl and
                (c["high"] - c["close"]) / total_range > 0.55):
                if candles_ago < best_recency:
                    best_recency = candles_ago
                    best_hunt = {
                        "detected":    True,
                        "type":        "BEARISH_SWEEP",
                        "level":       lvl,
                        "candles_ago": candles_ago,
                        "desc":        f"空方流動性獵殺：突破壓力 ${lvl:,.0f} 後反轉收回（多頭止損被掃）",
                    }

    return best_hunt or {"detected": False, "desc": "無明顯假突破跡象"}


# ─────────────────────────────────────────────
# FVG
# ─────────────────────────────────────────────

def find_fvg(df: pd.DataFrame, lookback: int = 60) -> list:
    fvgs = []
    start = max(2, len(df) - lookback)
    for i in range(start, len(df)):
        c0, c2 = df.iloc[i], df.iloc[i - 2]
        if c0["low"] > c2["high"]:
            fvgs.append({"type": "BULLISH_FVG", "top": c0["low"],
                         "bottom": c2["high"], "time": df.index[i]})
        elif c0["high"] < c2["low"]:
            fvgs.append({"type": "BEARISH_FVG", "top": c2["low"],
                         "bottom": c0["high"], "time": df.index[i]})
    return fvgs[-5:]


# ─────────────────────────────────────────────
# Order Block
# ─────────────────────────────────────────────

def find_order_blocks(df: pd.DataFrame, atr: pd.Series, lookback: int = 60) -> list:
    obs = []
    start = max(3, len(df) - lookback)
    for i in range(start, len(df) - 3):
        candle  = df.iloc[i]
        atr_val = atr.iloc[i] if not np.isnan(atr.iloc[i]) else 0
        if candle["close"] < candle["open"]:
            next3 = all(df.iloc[i + j]["close"] > df.iloc[i + j]["open"] for j in range(1, 4))
            move  = df["high"].iloc[i + 3] - df["low"].iloc[i]
            if next3 and move > atr_val * 1.5:
                obs.append({"type": "BULLISH_OB", "top": candle["high"],
                             "bottom": candle["low"], "time": df.index[i]})
        elif candle["close"] > candle["open"]:
            next3 = all(df.iloc[i + j]["close"] < df.iloc[i + j]["open"] for j in range(1, 4))
            move  = df["high"].iloc[i] - df["low"].iloc[i + 3]
            if next3 and move > atr_val * 1.5:
                obs.append({"type": "BEARISH_OB", "top": candle["high"],
                             "bottom": candle["low"], "time": df.index[i]})
    return obs[-3:]


# ─────────────────────────────────────────────
# K 線型態
# ─────────────────────────────────────────────

def detect_candle_pattern(df: pd.DataFrame) -> Optional[str]:
    c, p    = df.iloc[-1], df.iloc[-2]
    body    = abs(c["close"] - c["open"])
    rng     = c["high"] - c["low"]
    if rng == 0:
        return None

    upper_wick = c["high"] - max(c["close"], c["open"])
    lower_wick = min(c["close"], c["open"]) - c["low"]
    body_ratio = body / rng

    if body_ratio < 0.35:
        if lower_wick > upper_wick * 2.5 and lower_wick / rng > 0.55:
            return "BULLISH_PIN_BAR"
        if upper_wick > lower_wick * 2.5 and upper_wick / rng > 0.55:
            return "BEARISH_PIN_BAR"
    if body_ratio < 0.10:
        return "DOJI"

    p_top    = max(p["close"], p["open"])
    p_bottom = min(p["close"], p["open"])
    c_top    = max(c["close"], c["open"])
    c_bottom = min(c["close"], c["open"])
    if c_top > p_top and c_bottom < p_bottom:
        if c["close"] > c["open"] and p["close"] < p["open"]:
            return "BULLISH_ENGULFING"
        if c["close"] < c["open"] and p["close"] > p["open"]:
            return "BEARISH_ENGULFING"
    if body_ratio > 0.80:
        return "BULLISH_MARUBOZU" if c["close"] > c["open"] else "BEARISH_MARUBOZU"

    return None


# ─────────────────────────────────────────────
# 關鍵價位工具
# ─────────────────────────────────────────────

def get_key_levels(swing_highs: list, swing_lows: list, n: int = 5) -> dict:
    return {
        "resistances": sorted([s["price"] for s in swing_highs[-n:]], reverse=True),
        "supports":    sorted([s["price"] for s in swing_lows[-n:]],  reverse=True),
    }


def near_key_level(price: float, levels: list, tolerance: float = 0.006) -> bool:
    return any(abs(price - lvl) / lvl < tolerance for lvl in levels)


def price_zone(price: float, swing_highs: list, swing_lows: list) -> str:
    if not swing_highs or not swing_lows:
        return "UNKNOWN"
    high = max(s["price"] for s in swing_highs[-5:])
    low  = min(s["price"] for s in swing_lows[-5:])
    mid  = (high + low) / 2
    if price > mid:
        return "PREMIUM"
    if price < mid:
        return "DISCOUNT"
    return "EQUILIBRIUM"


def next_resistance_above(price: float, resistances: list) -> Optional[float]:
    candidates = [r for r in resistances if r > price * 1.001]
    return min(candidates, default=None)


def next_support_below(price: float, supports: list) -> Optional[float]:
    candidates = [s for s in supports if s < price * 0.999]
    return max(candidates, default=None)
