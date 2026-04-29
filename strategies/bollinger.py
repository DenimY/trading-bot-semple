"""볼린저 밴드 전략"""
import pandas as pd
from strategies.base import BaseStrategy


class BollingerStrategy(BaseStrategy):
    name = "bollinger"
    description = "볼린저 밴드 하단 터치 시 매수, 상단 터치 시 매도"

    def __init__(self, window: int = 20, num_std: float = 2.0):
        self.window = window
        self.num_std = num_std

    def generate_signal(self, ohlcv: pd.DataFrame) -> str:
        df = self.compute_indicators(ohlcv)
        if df["upper"].isna().all():
            return "HOLD"

        row = df.iloc[-1]
        prev = df.iloc[-2] if len(df) >= 2 else row

        if prev["close"] >= prev["lower"] and row["close"] < row["lower"]:
            return "BUY"
        if prev["close"] <= prev["upper"] and row["close"] > row["upper"]:
            return "SELL"
        return "HOLD"

    def compute_indicators(self, ohlcv: pd.DataFrame) -> pd.DataFrame:
        df = ohlcv.copy()
        df["mid"] = df["close"].rolling(self.window).mean()
        std = df["close"].rolling(self.window).std()
        df["upper"] = df["mid"] + self.num_std * std
        df["lower"] = df["mid"] - self.num_std * std
        return df
