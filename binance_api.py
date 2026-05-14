"""
binance_api.py — Binance 公開 API 資料抓取模組
"""

import time
import logging
import requests
import pandas as pd

logger = logging.getLogger(__name__)

class BinanceAPI:
    """Binance 公開 REST API 封裝，無需 API Key"""

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
        url = f"{self.base_url}/api/v3/klines"
        params = {
            "symbol":   self.symbol,
            "interval": interval,
            "limit":    min(limit, 1000),
        }

        for attempt in range(3):
            try:
                resp = self.session.get(url, params=params, timeout=10)
                resp.raise_for_status()
                raw = resp.json()
                return self._parse(raw)
            except Exception as exc:
                logger.warning("Binance API attempt %d failed: %s", attempt + 1, exc)
                if attempt < 2:
                    time.sleep(2 ** attempt)

        raise RuntimeError(f"Failed to fetch klines for {self.symbol} {interval}")

    def get_current_price(self) -> float:
        """取得最新成交價"""
        url = f"{self.base_url}/api/v3/ticker/price"
        resp = self.session.get(url, params={"symbol": self.symbol}, timeout=10)
        resp.raise_for_status()
        return float(resp.json()["price"])

    @staticmethod
    def _parse(raw: list) -> pd.DataFrame:
        cols = ["open_time","open","high","low","close","volume",
                "close_time","quote_vol","trades","buy_base","buy_quote","ignore"]
        df = pd.DataFrame(raw, columns=cols)
        df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
        df.set_index("open_time", inplace=True)
        for col in ["open","high","low","close","volume"]:
            df[col] = df[col].astype(float)
        return df[["open","high","low","close","volume"]]
