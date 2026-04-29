"""전략 베이스 클래스"""
from abc import ABC, abstractmethod
import pandas as pd


class BaseStrategy(ABC):
    name: str = "base"
    description: str = ""

    @abstractmethod
    def generate_signal(self, ohlcv: pd.DataFrame) -> str:
        """
        OHLCV 데이터를 받아 매매 신호 반환.
        반환값: "BUY" | "SELL" | "HOLD"
        """

    def compute_indicators(self, ohlcv: pd.DataFrame) -> pd.DataFrame:
        """UI 차트용 지표를 포함한 DataFrame 반환 (선택 구현)"""
        return ohlcv.copy()
