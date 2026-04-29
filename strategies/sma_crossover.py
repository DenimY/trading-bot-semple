"""단순 이동평균선 교차 전략 (SMA Crossover)"""
import pandas as pd
from strategies.base import BaseStrategy


class SMACrossoverStrategy(BaseStrategy):
    name = "sma_crossover"
    description = "단기/장기 이동평균선 교차 시 매수/매도"

    def __init__(self, short_window: int = 5, long_window: int = 20):
        self.short_window = short_window
        self.long_window = long_window

    def generate_signal(self, ohlcv: pd.DataFrame) -> str:
        df = self.compute_indicators(ohlcv)
        if len(df) < 2:
            return "HOLD"

        prev = df.iloc[-2]
        curr = df.iloc[-1]

        if prev["sma_short"] <= prev["sma_long"] and curr["sma_short"] > curr["sma_long"]:
            return "BUY"
        if prev["sma_short"] >= prev["sma_long"] and curr["sma_short"] < curr["sma_long"]:
            return "SELL"
        return "HOLD"

    def compute_indicators(self, ohlcv: pd.DataFrame) -> pd.DataFrame:
        df = ohlcv.copy()
        df["sma_short"] = df["close"].rolling(self.short_window).mean()
        df["sma_long"] = df["close"].rolling(self.long_window).mean()
        return df
