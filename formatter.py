"""
formatter.py — Telegram 訊息格式化
台灣時間（UTC+8）、整潔 SOP 清單、明確進場位
"""

from datetime import datetime, timezone, timedelta
from typing import Optional

TWN = timezone(timedelta(hours=8))


# ─── 基本工具 ─────────────────────────────────

def _now() -> str:
    return datetime.now(TWN).strftime("%m/%d %H:%M")

def _p(v) -> str:
    return f"${v:,.0f}" if v is not None else "—"

def _pct(v: float, sign: bool = False) -> str:
    s = "+" if sign and v > 0 else ("-" if sign and v < 0 else "")
    return f"{s}{abs(v):.2f}%"

def _chk(ok: bool) -> str:
    return "✅" if ok else "❌"

def _trend_icon(t: str) -> str:
    return {"UPTREND": "📈", "DOWNTREND": "📉", "RANGING": "↔️"}.get(t, "❓")

def _trend_tw(t: str) -> str:
    return {"UPTREND": "多頭", "DOWNTREND": "空頭", "RANGING": "盤整"}.get(t, t)

def _dir_icon(d: str) -> str:
    return {"LONG": "🟢", "SHORT": "🔴", "NEUTRAL": "⚪"}.get(d, "❓")

def _dir_tw(d: str) -> str:
    return {"LONG": "做多", "SHORT": "做空", "NEUTRAL": "觀望"}.get(d, d)

def _zone_tw(z: str) -> str:
    return {"PREMIUM": "溢價區", "DISCOUNT": "折價區",
            "EQUILIBRIUM": "均衡區", "UNKNOWN": "—"}.get(z, z)

def _pat_tw(p) -> str:
    m = {
        "BULLISH_PIN_BAR":   "錘子線",
        "BEARISH_PIN_BAR":   "流星線",
        "BULLISH_ENGULFING": "看多吞噬",
        "BEARISH_ENGULFING": "看空吞噬",
        "BULLISH_MARUBOZU":  "看多長實體",
        "BEARISH_MARUBOZU":  "看空長實體",
        "DOJI":              "十字星",
    }
    return m.get(p, p or "無")

def _bos_short(bos: Optional[dict]) -> str:
    if not bos:
        return "尚未確認"
    short = {"BOS_BULLISH": "多頭 BOS ✅", "BOS_BEARISH": "空頭 BOS ✅",
             "MSB_BULLISH": "多頭 MSB ⚠️", "MSB_BEARISH": "空頭 MSB ⚠️"}
    return short.get(bos["type"], bos["desc"])


# ─────────────────────────────────────────────
# 完整日線報告
# ─────────────────────────────────────────────

def format_full_analysis(analysis: dict, symbol: str = "BTC/USDT") -> str:
    daily = analysis["daily"]
    tf4h  = analysis["tf4h"]
    tf1h  = analysis["tf1h"]
    tf15m = analysis["tf15m"]
    tf5m  = analysis["tf5m"]
    hunt  = analysis["liquidity_hunt"]
    sig   = analysis["signal"]
    price = analysis["current_price"]
    sop   = sig["sop_checks"]

    trend_i = _trend_icon(daily["trend"])
    dir_i   = _dir_icon(sig["direction"])

    lines = [
        f"━━━━━━━━━━━━━━━━━━━━",
        f"📊 *{symbol} 價格行為分析*",
        f"⏰ {_now()}（台灣時間）",
        f"💰 現價 *{_p(price)}*　{trend_i} {_trend_tw(daily['trend'])}",
        f"━━━━━━━━━━━━━━━━━━━━",
        f"",
        f"*SOP 檢查 {sig['score']}/9*",
    ]

    # SOP 9步
    sop_rows = [
        ("trend",         "日線趨勢"),
        ("sr_map",        "支撐／阻力"),
        ("zone",          "供需區"),
        ("mid_structure", "4H／1H 結構"),
        ("small_signal",  "15m／5m 信號"),
        ("liquidity",     "流動性偵測"),
        ("sl",            "止損位"),
        ("tp",            "止盈位"),
        ("rr",            "R:R"),
    ]
    for key, label in sop_rows:
        ok, desc = sop.get(key, (False, "—"))
        lines.append(f"{_chk(ok)} *{label}*　{desc}")

    # 各時間框架概況
    lines += [
        f"",
        f"*各框架概況*",
        f"日線　{_trend_tw(daily['trend'])}｜位置 {_zone_tw(daily['zone'])}",
        f"　阻力 {_p(daily['nearest_resistance'])}　支撐 {_p(daily['nearest_support'])}",
    ]
    if daily["supply_zone"]:
        sz = daily["supply_zone"]
        lines.append(f"　供給區 {_p(sz['bottom'])}–{_p(sz['top'])} [{sz['quality']}]")
    if daily["demand_zone"]:
        dz = daily["demand_zone"]
        lines.append(f"　需求區 {_p(dz['bottom'])}–{_p(dz['top'])} [{dz['quality']}]")

    lines += [
        f"4H　{_trend_tw(tf4h['trend'])}｜{_bos_short(tf4h['bos'])}",
        f"1H　{_trend_tw(tf1h['trend'])}｜{_bos_short(tf1h['bos'])}",
        f"15m {_pat_tw(tf15m['pattern'])}　5m {_pat_tw(tf5m['pattern'])}",
        f"流動性　{hunt['desc']}",
        f"",
    ]

    # 進場決策
    lines.append("*─ 進場決策 ─*")

    if sig["risk_too_high"]:
        lines += [
            f"",
            f"⛔ *此次不做*",
            f"原因：{sig['skip_reason']}",
            f"建議：等待回調至更近的進場位",
        ]
    elif sig["has_signal"] and sig["sl"] and sig["tp1"]:
        sl_diff  = abs(price - sig["sl"])
        tp1_diff = abs(price - sig["tp1"])
        lines += [
            f"",
            f"{dir_i} *{_dir_tw(sig['direction'])}信號*",
            f"",
            f"進場　*{_p(sig['entry'])}*",
            f"止損　*{_p(sig['sl'])}*　{'▲' if sig['sl'] > price else '▼'}{_p(sl_diff)} ({_pct(sig['sl_pct'])})",
            f"止盈　*{_p(sig['tp1'])}*　{'▲' if sig['tp1'] > price else '▼'}{_p(tp1_diff)} ({_pct(sig['tp1_pct'])}) 　R:R *1:{sig['rr1']:.1f}*",
        ]
    else:
        missing = [label for (key, label), (ok, _) in
                   zip(sop_rows, [sop.get(k, (False, "")) for k, _ in sop_rows])
                   if not ok]
        lines += [
            f"",
            f"⏸ *此次不做*",
            f"未達條件：{' / '.join(missing[:3]) if missing else '綜合評估不足'}",
            f"評分 {sig['score']}/9，需 ≥ 6 且 R:R ≥ 1:2",
        ]

    lines += [
        f"",
        f"━━━━━━━━━━━━━━━━━━━━",
        f"_⚠️ 僅供參考，交易有風險_",
    ]

    return "\n".join(lines)


# ─────────────────────────────────────────────
# 強信號 Alert（15m 掃描觸發）
# ─────────────────────────────────────────────

def format_signal_alert(analysis: dict, symbol: str = "BTC/USDT") -> str:
    sig   = analysis["signal"]
    daily = analysis["daily"]
    price = analysis["current_price"]
    sop   = sig["sop_checks"]
    dir_i = _dir_icon(sig["direction"])

    sl_diff  = abs(price - sig["sl"])
    tp1_diff = abs(price - sig["tp1"])

    lines = [
        f"🚨 *{symbol} 進場信號*",
        f"⏰ {_now()}（台灣時間）",
        f"━━━━━━━━━━━━━━━━━━━━",
        f"{dir_i} *{_dir_tw(sig['direction'])}*　SOP {sig['score']}/9",
        f"",
        f"進場　*{_p(price)}*",
        f"止損　*{_p(sig['sl'])}*　{'▲' if sig['sl'] > price else '▼'}{_p(sl_diff)} ({_pct(sig['sl_pct'])})",
        f"止盈　*{_p(sig['tp1'])}*　{'▲' if sig['tp1'] > price else '▼'}{_p(tp1_diff)} ({_pct(sig['tp1_pct'])})　R:R *1:{sig['rr1']:.1f}*",
        f"",
        f"止損 1R → 止盈 {sig['rr1']:.1f}R ✅",
        f"",
        f"*市場背景*",
        f"日線 {_trend_icon(daily['trend'])} {_trend_tw(daily['trend'])}　位置 {_zone_tw(daily['zone'])}",
    ]

    if daily.get("supply_zone") and sig["direction"] == "SHORT":
        sz = daily["supply_zone"]
        lines.append(f"供給區 {_p(sz['bottom'])}–{_p(sz['top'])} [{sz['quality']}]")
    if daily.get("demand_zone") and sig["direction"] == "LONG":
        dz = daily["demand_zone"]
        lines.append(f"需求區 {_p(dz['bottom'])}–{_p(dz['top'])} [{dz['quality']}]")

    # SOP 快速核對
    sop_rows = [
        ("trend", "日線趨勢"), ("mid_structure", "4H/1H 結構"),
        ("small_signal", "15m/5m 信號"), ("liquidity", "流動性"),
        ("sl", "止損位"), ("tp", "止盈位"), ("rr", "R:R"),
    ]
    lines.append(f"")
    lines.append(f"*SOP 核對*")
    for key, label in sop_rows:
        ok, desc = sop.get(key, (False, "—"))
        lines.append(f"{_chk(ok)} {label}　{desc}")


    lines += [
        f"",
        f"━━━━━━━━━━━━━━━━━━━━",
        f"_⚠️ 僅供參考，請設置好風控再進場_",
    ]

    return "\n".join(lines)


# ─────────────────────────────────────────────
# 風險過高通知
# ─────────────────────────────────────────────

def format_risk_skip(analysis: dict, symbol: str = "BTC/USDT") -> str:
    sig   = analysis["signal"]
    price = analysis["current_price"]
    daily = analysis["daily"]

    lines = [
        f"⛔ *{symbol} 風險過高，此次不做*",
        f"⏰ {_now()}（台灣時間）",
        f"━━━━━━━━━━━━━━━━━━━━",
        f"💰 {_p(price)}　{_trend_icon(daily['trend'])} {_trend_tw(daily['trend'])}",
        f"",
        f"原因：{sig['skip_reason']}",
        f"",
        f"方向偏向：{_dir_tw(sig['direction'])}（SOP {sig['score']}/9）",
        f"止損位：{_p(sig['sl'])}（距離 {_pct(sig['sl_pct'])}，超過上限 2.5%）",
        f"",
        f"建議：等待回調後在更近位置重新評估",
        f"━━━━━━━━━━━━━━━━━━━━",
    ]
    return "\n".join(lines)
