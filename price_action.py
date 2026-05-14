"""
price_action.py — 9步 SOP 價格行為學分析引擎

SOP：
  [1] 大週期趨勢方向確認（日線）
  [2] 支撐壓力地圖標記
  [3] 供需區位置與品質確認
  [4] 中週期結構確認（4h / 1h）
  [5] 小週期 K 線訊號出現（15m / 5m）
  [6] 流動性獵殺跡象偵測（假突破）
  [7] 止損位確定（結構失效點外 + 0.3% 緩衝）
  [8] 止盈位確定（下一供需區前）
  [9] R:R ≥ 1:2 強制過濾
"""

import logging
import numpy as np
import pandas as pd
from typing import Optional

from patterns import (
    calc_atr, find_swing_points, determine_trend,
    detect_bos, find_fvg, find_order_blocks,
    find_supply_demand_zones,
    detect_liquidity_hunt,
    detect_candle_pattern,
    get_key_levels, near_key_level, price_zone,
    next_resistance_above, next_support_below,
    nearest_zone_above, nearest_zone_below,
)
from config import (
    SWING_LOOKBACK_DAILY, SWING_LOOKBACK_4H, SWING_LOOKBACK_1H,
    SWING_LOOKBACK_15M,  SWING_LOOKBACK_5M,
    ATR_PERIOD, SL_BUFFER_PCT, MIN_RR_RATIO, MAX_SL_PCT,
    KEY_LEVEL_TOLERANCE, LIQUIDITY_HUNT_BARS,
)

logger = logging.getLogger(__name__)


class PriceActionAnalyzer:

    def run_sop(self,
                daily_df: pd.DataFrame,
                tf4h_df:  pd.DataFrame,
                tf1h_df:  pd.DataFrame,
                tf15m_df: pd.DataFrame,
                tf5m_df:  pd.DataFrame,
                current_price: Optional[float] = None) -> dict:
        """執行完整 9 步 SOP，回傳結構化分析結果"""

        price = current_price or daily_df["close"].iloc[-1]
        result = {"current_price": price}

        # ── [1][2][3] 日線分析 ─────────────────────
        result["daily"] = self._step123_daily(daily_df, price)

        # ── [4] 中週期：4H + 1H ────────────────────
        result["tf4h"]  = self._step4_mid(tf4h_df,  SWING_LOOKBACK_4H,  result["daily"]["trend"])
        result["tf1h"]  = self._step4_mid(tf1h_df,  SWING_LOOKBACK_1H,  result["daily"]["trend"])

        # ── [5] 小週期：15m + 5m ───────────────────
        result["tf15m"] = self._step5_small(tf15m_df, SWING_LOOKBACK_15M, result["daily"]["trend"])
        result["tf5m"]  = self._step5_small(tf5m_df,  SWING_LOOKBACK_5M,  result["daily"]["trend"])

        # ── [6] 流動性獵殺 ─────────────────────────
        sh_daily = result["daily"]["swing_highs"]
        sl_daily = result["daily"]["swing_lows"]
        result["liquidity_hunt"] = detect_liquidity_hunt(
            tf15m_df, sh_daily, sl_daily, LIQUIDITY_HUNT_BARS
        )

        # ── [7][8][9] 進場信號整合 ─────────────────
        result["signal"] = self._steps789_signal(result, price)

        return result

    # ══════════════════════════════════════════
    # Step 1-3：日線分析
    # ══════════════════════════════════════════

    def _step123_daily(self, df: pd.DataFrame, price: float) -> dict:
        atr     = calc_atr(df, ATR_PERIOD)
        sh, sl  = find_swing_points(df, SWING_LOOKBACK_DAILY)
        trend   = determine_trend(sh, sl)
        levels  = get_key_levels(sh, sl, n=5)
        bos     = detect_bos(df, sh, sl, trend)
        zones   = find_supply_demand_zones(df, atr, lookback=100)
        zone    = price_zone(price, sh, sl)

        # 最近支撐與阻力
        nr = next_resistance_above(price, levels["resistances"])
        ns = next_support_below(price,   levels["supports"])

        # 鄰近供需區
        supply = nearest_zone_above(price, [z for z in zones if z["type"] == "SUPPLY_ZONE"])
        demand = nearest_zone_below(price, [z for z in zones if z["type"] == "DEMAND_ZONE"])

        return {
            "trend":              trend,
            "zone":               zone,
            "swing_highs":        sh,
            "swing_lows":         sl,
            "resistances":        levels["resistances"],
            "supports":           levels["supports"],
            "nearest_resistance": nr,
            "nearest_support":    ns,
            "supply_zone":        supply,
            "demand_zone":        demand,
            "all_zones":          zones,
            "bos":                bos,
            "atr":                float(atr.iloc[-1]),
            "atr_pct":            float(atr.iloc[-1] / price * 100),
        }

    # ══════════════════════════════════════════
    # Step 4：中週期（4H / 1H）
    # ══════════════════════════════════════════

    def _step4_mid(self, df: pd.DataFrame, lookback: int, daily_trend: str) -> dict:
        atr     = calc_atr(df, ATR_PERIOD)
        sh, sl  = find_swing_points(df, lookback)
        trend   = determine_trend(sh, sl)
        bos     = detect_bos(df, sh, sl, trend)
        fvgs    = find_fvg(df, lookback=60)
        obs     = find_order_blocks(df, atr, lookback=60)
        zones   = find_supply_demand_zones(df, atr, lookback=80)

        aligned = (trend == daily_trend) or \
                  (daily_trend != "RANGING" and trend == daily_trend)

        return {
            "trend":        trend,
            "aligned":      aligned,
            "bos":          bos,
            "fvgs":         fvgs,
            "order_blocks": obs,
            "zones":        zones,
            "swing_highs":  sh,
            "swing_lows":   sl,
            "atr":          float(atr.iloc[-1]),
        }

    # ══════════════════════════════════════════
    # Step 5：小週期（15m / 5m）
    # ══════════════════════════════════════════

    def _step5_small(self, df: pd.DataFrame, lookback: int, daily_trend: str) -> dict:
        atr     = calc_atr(df, ATR_PERIOD)
        sh, sl  = find_swing_points(df, lookback)
        trend   = determine_trend(sh, sl)
        pattern = detect_candle_pattern(df)
        bos     = detect_bos(df, sh, sl, trend)

        valid = False
        if pattern:
            if daily_trend == "UPTREND"   and "BULLISH" in pattern:
                valid = True
            elif daily_trend == "DOWNTREND" and "BEARISH" in pattern:
                valid = True
            elif daily_trend == "RANGING":
                valid = True

        return {
            "trend":         trend,
            "pattern":       pattern,
            "valid_pattern": valid,
            "bos":           bos,
            "swing_highs":   sh,
            "swing_lows":    sl,
            "atr":           float(atr.iloc[-1]),
        }

    # ══════════════════════════════════════════
    # Step 7-8-9：SL / TP 計算 + R:R 過濾
    # ══════════════════════════════════════════

    def _steps789_signal(self, r: dict, price: float) -> dict:
        daily = r["daily"]
        tf4h  = r["tf4h"]
        tf1h  = r["tf1h"]
        tf15m = r["tf15m"]
        tf5m  = r["tf5m"]
        hunt  = r["liquidity_hunt"]
        trend = daily["trend"]

        # ── 方向決定 ──────────────────────────────
        direction = "NEUTRAL"
        if trend == "UPTREND":
            direction = "LONG"
        elif trend == "DOWNTREND":
            direction = "SHORT"

        # 流動性獵殺可反轉方向
        if hunt["detected"]:
            if hunt["type"] == "BULLISH_SWEEP":
                direction = "LONG"
            elif hunt["type"] == "BEARISH_SWEEP":
                direction = "SHORT"

        # ── SOP 評分 ──────────────────────────────
        sop_checks = {}

        sop_checks["trend"] = (trend != "RANGING",
                                f"{_trend_label(trend)}")

        sop_checks["sr_map"] = (bool(daily["nearest_resistance"] or daily["nearest_support"]),
                                 f"阻力 {_p(daily['nearest_resistance'])} | 支撐 {_p(daily['nearest_support'])}")

        best_zone = daily["demand_zone"] if direction == "LONG" else daily["supply_zone"]
        sop_checks["zone"] = (best_zone is not None,
                               f"{best_zone['type'] if best_zone else '未偵測到'}" +
                               (f" {_p(best_zone['bottom'])}–{_p(best_zone['top'])} [{best_zone['quality']}]"
                                if best_zone else ""))

        mid_ok = (tf4h["aligned"] or tf1h["aligned"]) and \
                 (tf4h["bos"] is not None or tf1h["bos"] is not None)
        mid_desc = []
        if tf4h["bos"]:
            mid_desc.append(f"4H {tf4h['bos']['desc']}")
        if tf1h["bos"]:
            mid_desc.append(f"1H {tf1h['bos']['desc']}")
        if not mid_desc:
            mid_desc.append(f"4H {'對齊' if tf4h['aligned'] else '未對齊'} | 1H {'對齊' if tf1h['aligned'] else '未對齊'}")
        sop_checks["mid_structure"] = (mid_ok or tf4h["aligned"] or tf1h["aligned"],
                                        " | ".join(mid_desc))

        small_ok = tf15m["valid_pattern"] or tf5m["valid_pattern"]
        pattern  = tf5m["pattern"] or tf15m["pattern"]
        sop_checks["small_signal"] = (small_ok,
                                       f"15m {_pat(tf15m['pattern'])} | 5m {_pat(tf5m['pattern'])}")

        sop_checks["liquidity"] = (True,
                                    hunt["desc"])

        # ── Step 7：計算 SL（結構失效點外）────────
        sl_price = self._calc_sl(price, direction, daily, tf4h, tf1h, tf5m)

        sop_checks["sl"] = (sl_price is not None,
                             _p(sl_price) + " (結構失效點外)" if sl_price else "未能確定")

        # ── Step 8：計算 TP（下一供需區前）─────────
        tp1, tp2 = None, None
        if sl_price:
            risk = abs(price - sl_price)   # = 1R
            tp1, tp2 = self._calc_tp(price, direction, risk, daily)

        sop_checks["tp"] = (tp1 is not None,
                             f"{_p(tp1)}（固定 2R）" if tp1 else "未能計算")

        # ── Step 9：R:R 強制過濾 ─────────────────
        rr1 = 0.0
        if sl_price and tp1:
            risk   = abs(price - sl_price)
            reward = abs(price - tp1)
            rr1    = reward / risk if risk else 0

        rr_ok = rr1 >= MIN_RR_RATIO
        sop_checks["rr"] = (rr_ok,
                             f"1:{rr1:.1f}" + (" ✅" if rr_ok else f" ❌（未達 1:{MIN_RR_RATIO:.0f}）"))

        # ── 風險過高過濾 ─────────────────────────
        sl_pct       = abs(price - sl_price) / price * 100 if sl_price else 0
        risk_too_high = sl_pct > MAX_SL_PCT * 100
        skip_reason   = (f"止損距離 {sl_pct:.1f}% 超過上限 {MAX_SL_PCT*100:.0f}%，風險過高"
                         if risk_too_high else None)

        # ── 最終評分 ─────────────────────────────
        score      = sum(1 for v, _ in sop_checks.values() if v)
        has_signal = (score >= 6 and direction != "NEUTRAL" and
                      sl_price is not None and tp1 is not None and
                      rr_ok and not risk_too_high)

        strength = ("STRONG"    if score >= 8 else
                    "MODERATE"  if score >= 6 else
                    "WEAK"      if score >= 4 else "NO_SIGNAL")

        tp1_pct = abs(price - tp1) / price * 100 if tp1 else 0

        return {
            "has_signal":    has_signal,
            "risk_too_high": risk_too_high,
            "skip_reason":   skip_reason,
            "direction":     direction,
            "strength":      strength,
            "score":         score,
            "sop_checks":    sop_checks,
            "entry":         price,
            "sl":            sl_price,
            "tp1":           tp1,
            "sl_pct":        sl_pct,
            "tp1_pct":       tp1_pct,
            "rr1":           rr1,
        }

    # ══════════════════════════════════════════
    # 止損計算（Step 7）
    # ══════════════════════════════════════════

    def _calc_sl(self, price: float, direction: str,
                 daily: dict, tf4h: dict, tf1h: dict, tf5m: dict) -> Optional[float]:
        """
        SL = 最近一個結構失效點（swing low/high）外加緩衝
        優先用 5m 精準低/高點，其次 1H，再次日線
        """
        if direction == "LONG":
            candidates = []
            for sl_list in [tf5m["swing_lows"], tf1h["swing_lows"], daily["swing_lows"]]:
                lows_below = [s["price"] for s in sl_list if s["price"] < price]
                if lows_below:
                    candidates.append(max(lows_below))
            if candidates:
                struct_low = max(candidates)
                return struct_low * (1 - SL_BUFFER_PCT)

        elif direction == "SHORT":
            candidates = []
            for sh_list in [tf5m["swing_highs"], tf1h["swing_highs"], daily["swing_highs"]]:
                highs_above = [s["price"] for s in sh_list if s["price"] > price]
                if highs_above:
                    candidates.append(min(highs_above))
            if candidates:
                struct_high = min(candidates)
                return struct_high * (1 + SL_BUFFER_PCT)

        return None

    # ══════════════════════════════════════════
    # 止盈計算（Step 8）
    # ══════════════════════════════════════════

    def _calc_tp(self, price: float, direction: str,
                 risk: float, daily: dict) -> tuple[Optional[float], Optional[float]]:
        """
        TP 固定鎖在 2R（不追遠區間，避免持倉時間過長）。
        供需區只做「是否有阻礙」的參考：
          - 若下一供需區在 2R 之前，則提前在區前 0.1% 離場（縮短到 1.5R~1.9R）。
          - 若供需區比 2R 更遠或不存在，直接用 2R 位置出場。
        TP2 不設置（小週期單邊交易不需要持倉等待 3R）。
        """
        tp_target = price + risk * 2.0 if direction == "LONG" else price - risk * 2.0

        if direction == "LONG":
            # 檢查 2R 之前是否有供給區阻礙
            sz = daily["supply_zone"]
            if sz and sz["bottom"] > price and sz["bottom"] < tp_target:
                # 在供給區底部前 0.1% 出場
                tp1 = sz["bottom"] * 0.999
            else:
                tp1 = tp_target
        else:
            # 檢查 2R 之前是否有需求區阻礙
            dz = daily["demand_zone"]
            if dz and dz["top"] < price and dz["top"] > tp_target:
                tp1 = dz["top"] * 1.001
            else:
                tp1 = tp_target

        return tp1, None  # TP2 不設置，專注 2R 快速出場


# ── helpers ──────────────────────────────────

def _trend_label(t: str) -> str:
    return {"UPTREND": "多頭上升趨勢", "DOWNTREND": "空頭下降趨勢",
            "RANGING": "盤整橫盤"}.get(t, t)

def _p(v) -> str:
    return f"${v:,.0f}" if v else "—"

def _pat(p) -> str:
    m = {"BULLISH_PIN_BAR": "看多針棒", "BEARISH_PIN_BAR": "看空針棒",
         "BULLISH_ENGULFING": "看多吞噬", "BEARISH_ENGULFING": "看空吞噬",
         "BULLISH_MARUBOZU": "看多長實體", "BEARISH_MARUBOZU": "看空長實體",
         "DOJI": "十字星"}
    return m.get(p, p or "無型態")
