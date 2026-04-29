"""모의투자 브로커: 전략 신호를 받아 주문 실행"""
from data.fetcher import get_current_price, get_ohlcv
from core.portfolio import Portfolio
from strategies.base import BaseStrategy
from data import storage


class PaperBroker:
    def __init__(self, portfolio: Portfolio, strategy: BaseStrategy,
                 order_amount: float = 500_000,
                 max_position_pct: float = 20.0):
        self.portfolio = portfolio
        self.strategy = strategy
        self.order_amount = order_amount          # 1회 매수 금액
        self.max_position_pct = max_position_pct  # 총자산 대비 최대 종목 비중 (%)

    def run_once(self, ticker: str) -> str:
        """단일 종목에 대해 신호 확인 후 주문"""
        ohlcv = get_ohlcv(ticker, days=120)
        if ohlcv.empty or len(ohlcv) < 30:
            return "데이터 부족"

        signal = self.strategy.generate_signal(ohlcv)
        price = get_current_price(ticker)
        if price <= 0:
            return "현재가 조회 실패"

        snap = self.portfolio.get_snapshot()
        total_assets = snap["total_assets"]

        if signal == "BUY":
            # 최대 비중 초과 방지
            holdings = {h["ticker"]: h for h in snap["holdings"]}
            cur_eval = holdings[ticker]["eval_amount"] if ticker in holdings else 0
            if cur_eval / total_assets * 100 >= self.max_position_pct:
                return f"HOLD (최대 비중 {self.max_position_pct}% 초과)"

            cash = self.portfolio.get_cash()
            buy_amount = min(self.order_amount, cash * 0.95)
            qty = int(buy_amount // price)
            if qty <= 0:
                return "잔고 부족"
            result = self.portfolio.execute_buy(ticker, qty, price, self.strategy.name)
            return f"BUY {qty}주 @ {price:,.0f}원 → {result}"

        elif signal == "SELL":
            holdings = {h["ticker"]: h for h in snap["holdings"]}
            if ticker not in holdings:
                return "HOLD (미보유)"
            qty = holdings[ticker]["quantity"]
            result = self.portfolio.execute_sell(ticker, qty, price, self.strategy.name)
            return f"SELL {qty}주 @ {price:,.0f}원 → {result}"

        return "HOLD"

    def run_all(self, tickers: list[str]) -> dict[str, str]:
        """감시 종목 전체 실행"""
        results = {}
        for t in tickers:
            try:
                results[t] = self.run_once(t)
            except Exception as e:
                results[t] = f"오류: {e}"
        return results


def get_watchlist() -> list[str]:
    return storage.get_state("watchlist", [])


def set_watchlist(tickers: list[str]):
    storage.set_state("watchlist", tickers)
