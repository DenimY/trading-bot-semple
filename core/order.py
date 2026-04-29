"""주문 모델"""
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Order:
    ticker: str
    name: str
    side: str          # "BUY" | "SELL"
    quantity: int
    price: float
    strategy: str = ""
    executed_at: str = ""

    def __post_init__(self):
        if not self.executed_at:
            self.executed_at = datetime.now().isoformat(timespec="seconds")

    @property
    def amount(self) -> float:
        return self.quantity * self.price
