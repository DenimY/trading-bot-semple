"""RSI 과매수/과매도 전략"""
import pandas as pd
from strategies.base import BaseStrategy


class RSIStrategy(BaseStrategy):
    name = "rsi"
    description = "RSI 지표 기반 과매수/과매도 매매"

    def __init__(self, period: int = 14, oversold: float = 30, overbought: float = 70):
        self.period = period
        self.oversold = oversold
        self.overbought = overbought

    def _calc_rsi(self, series: pd.Series) -> pd.Series:
        delta = series.diff()
        gain = delta.clip(lower=0).rolling(self.period).mean()
        loss = (-delta.clip(upper=0)).rolling(self.period).mean()
        rs = gain / loss.replace(0, float("nan"))
        return 100 - (100 / (1 + rs))

    def generate_signal(self, ohlcv: pd.DataFrame) -> str:
        df = self.compute_indicators(ohlcv)
        if df["rsi"].isna().all():
            return "HOLD"

        rsi = df["rsi"].iloc[-1]
        prev_rsi = df["rsi"].iloc[-2] if len(df) >= 2 else rsi

        if prev_rsi < self.oversold and rsi >= self.oversold:
            return "BUY"
        if prev_rsi > self.overbought and rsi <= self.overbought:
            return "SELL"
        return "HOLD"

    def compute_indicators(self, ohlcv: pd.DataFrame) -> pd.DataFrame:
        df = ohlcv.copy()
        df["rsi"] = self._calc_rsi(df["close"])
        df["oversold"] = self.oversold
        df["overbought"] = self.overbought
        return df
