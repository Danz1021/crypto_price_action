"""
binance_api.py — Bybit 公開 API 資料抓取模組
（原 Binance API 因 GitHub Actions 美國 IP 被 451 封鎖，改用 Bybit）
"""

import time
import logging
import requests
import pandas as pd

logger = logging.getLogger(__name__)

# Bybit interval 對照表
_INTERVAL_MAP = {
    "1d":  "D",
    "4h":  "240",
    "1h":  "60",
    "15m": "15",
    "5m":  "5",
}


class BinanceAPI:
    """Bybit V5 公開 REST API 封裝，無需 API Key"""

    def __init__(self, base_url: str, symbol: str):
        self.base_url = base_url
        self.symbol   = symbol
        self.session  = requests.Session()
        self.session.headers.update({"Accept": "application/json"})

    def get_klines(self, interval: str, limit: int = 300) -> pd.DataFrame:
        """
        取得 K 線資料並回傳 DataFrame。
        欄位：open, high, low, close, volume，index 為 UTC datetime。
        """
        bybit_interval = _INTERVAL_MAP.get(interval, interval)
        url    = f"{self.base_url}/v5/market/kline"
        params = {
            "category": "spot",
            "symbol":   self.symbol,
            "interval": bybit_interval,
            "limit":    min(limit, 1000),
        }

        for attempt in range(3):
            try:
                resp = self.session.get(url, params=params, timeout=10)
                resp.raise_for_status()
                data = resp.json()
                if data.get("retCode") != 0:
                    raise ValueError(f"Bybit error: {data.get('retMsg')}")
                return self._parse(data["result"]["list"])
            except Exception as exc:
                logger.warning("Bybit API attempt %d failed: %s", attempt + 1, exc)
                if attempt < 2:
                    time.sleep(2 ** attempt)

        raise RuntimeError(f"Failed to fetch klines for {self.symbol} {interval}")

    def get_current_price(self) -> float:
        """取得最新成交價"""
        url    = f"{self.base_url}/v5/market/tickers"
        params = {"category": "spot", "symbol": self.symbol}
        resp   = self.session.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return float(data["result"]["list"][0]["lastPrice"])

    @staticmethod
    def _parse(raw: list) -> pd.DataFrame:
        # Bybit 回傳格式：[startTime, open, high, low, close, volume, turnover]
        # 順序為新到舊，需要反轉
        rows = []
        for item in reversed(raw):
            rows.append({
                "open_time": int(item[0]),
                "open":      float(item[1]),
                "high":      float(item[2]),
                "low":       float(item[3]),
                "close":     float(item[4]),
                "volume":    float(item[5]),
            })

        df = pd.DataFrame(rows)
        df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
        df.set_index("open_time", inplace=True)
        return df[["open", "high", "low", "close", "volume"]]
