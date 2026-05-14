"""
binance_api.py — Kraken 公開 API 資料抓取模組
（Binance/Bybit 對 GitHub Actions 美國 IP 封鎖，改用 Kraken，無地區限制）
"""

import time
import logging
import requests
import pandas as pd

logger = logging.getLogger(__name__)

# Kraken interval（分鐘）對照表
_INTERVAL_MAP = {
    "1d":  1440,
    "4h":  240,
    "1h":  60,
    "15m": 15,
    "5m":  5,
}

KRAKEN_SYMBOL = "XBTUSD"   # Kraken 用 XBT 代替 BTC


class BinanceAPI:
    """Kraken 公開 REST API 封裝，無需 API Key，無地區限制"""

    def __init__(self, base_url: str, symbol: str):
        self.base_url = base_url
        self.symbol   = symbol
        self.session  = requests.Session()
        self.session.headers.update({"Accept": "application/json"})

    def get_klines(self, interval: str, limit: int = 300) -> pd.DataFrame:
        """
        取得 K 線資料並回傳 DataFrame。
        欄位：open, high, low, close, volume，index 為 UTC datetime。
        Kraken 每次最多回傳 720 根。
        """
        kraken_interval = _INTERVAL_MAP.get(interval, 60)
        url    = f"{self.base_url}/0/public/OHLC"
        params = {
            "pair":     KRAKEN_SYMBOL,
            "interval": kraken_interval,
        }

        for attempt in range(3):
            try:
                resp = self.session.get(url, params=params, timeout=10)
                resp.raise_for_status()
                data = resp.json()

                if data.get("error"):
                    raise ValueError(f"Kraken error: {data['error']}")

                # Kraken 實際回傳的 key 可能是 XXBTZUSD，動態取得
                result_key = next(k for k in data["result"] if k != "last")
                raw = data["result"][result_key]
                df  = self._parse(raw)

                # 只取最近 limit 根
                return df.iloc[-limit:] if len(df) > limit else df

            except Exception as exc:
                logger.warning("Kraken API attempt %d failed: %s", attempt + 1, exc)
                if attempt < 2:
                    time.sleep(2 ** attempt)

        raise RuntimeError(f"Failed to fetch klines for {self.symbol} {interval}")

    def get_current_price(self) -> float:
        """取得最新成交價"""
        url  = f"{self.base_url}/0/public/Ticker"
        resp = self.session.get(url, params={"pair": KRAKEN_SYMBOL}, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        # 'c' = [price, lot_volume]，key 動態取得
        result_key = next(k for k in data["result"])
        return float(data["result"][result_key]["c"][0])

    @staticmethod
    def _parse(raw: list) -> pd.DataFrame:
        # Kraken 格式：[time, open, high, low, close, vwap, volume, count]
        rows = []
        for item in raw:
            rows.append({
                "open_time": int(item[0]),
                "open":      float(item[1]),
                "high":      float(item[2]),
                "low":       float(item[3]),
                "close":     float(item[4]),
                "volume":    float(item[6]),
            })

        df = pd.DataFrame(rows)
        df["open_time"] = pd.to_datetime(df["open_time"], unit="s", utc=True)
        df.set_index("open_time", inplace=True)
        return df[["open", "high", "low", "close", "volume"]]
