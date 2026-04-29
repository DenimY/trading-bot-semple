"""포트폴리오 관리 (보유 종목, 현금, 손익 계산)"""
from data import storage
from data.fetcher import get_current_price, get_stock_name


class Portfolio:
    def get_cash(self) -> float:
        return storage.get_cash()

    def get_holdings(self) -> list[dict]:
        return storage.get_holdings()

    def get_snapshot(self) -> dict:
        """현재 포트폴리오 스냅샷 (현재가 기준 평가)"""
        holdings = self.get_holdings()
        rows = []
        total_eval = 0.0
        total_cost = 0.0

        for h in holdings:
            cur = get_current_price(h["ticker"])
            cost = h["avg_price"] * h["quantity"]
            eval_val = cur * h["quantity"]
            pnl = eval_val - cost
            pnl_pct = (pnl / cost * 100) if cost > 0 else 0.0
            rows.append({
                "ticker": h["ticker"],
                "name": h["name"],
                "quantity": h["quantity"],
                "avg_price": h["avg_price"],
                "current_price": cur,
                "eval_amount": eval_val,
                "pnl": pnl,
                "pnl_pct": pnl_pct,
            })
            total_eval += eval_val
            total_cost += cost

        cash = self.get_cash()
        total_assets = cash + total_eval
        total_pnl = total_eval - total_cost

        return {
            "holdings": rows,
            "cash": cash,
            "total_eval": total_eval,
            "total_assets": total_assets,
            "total_pnl": total_pnl,
            "total_pnl_pct": (total_pnl / total_cost * 100) if total_cost > 0 else 0.0,
        }

    def execute_buy(self, ticker: str, quantity: int, price: float, strategy: str = "") -> str:
        name = get_stock_name(ticker)
        cost = quantity * price
        cash = self.get_cash()
        if cash < cost:
            return f"잔고 부족: 필요 {cost:,.0f}원 / 보유 {cash:,.0f}원"

        # 평균 매수가 계산
        holdings = {h["ticker"]: h for h in self.get_holdings()}
        if ticker in holdings:
            h = holdings[ticker]
            new_qty = h["quantity"] + quantity
            new_avg = (h["avg_price"] * h["quantity"] + price * quantity) / new_qty
        else:
            new_qty = quantity
            new_avg = price

        storage.set_cash(cash - cost)
        storage.upsert_holding(ticker, name, new_qty, new_avg)
        storage.add_trade(ticker, name, "BUY", quantity, price, strategy)
        return "OK"

    def execute_sell(self, ticker: str, quantity: int, price: float, strategy: str = "") -> str:
        name = get_stock_name(ticker)
        holdings = {h["ticker"]: h for h in self.get_holdings()}
        if ticker not in holdings or holdings[ticker]["quantity"] < quantity:
            return "보유 수량 부족"

        h = holdings[ticker]
        new_qty = h["quantity"] - quantity
        cash = self.get_cash()
        storage.set_cash(cash + quantity * price)
        storage.upsert_holding(ticker, name, new_qty, h["avg_price"])
        storage.add_trade(ticker, name, "SELL", quantity, price, strategy)
        return "OK"

    def reset(self, initial_cash: float):
        storage.reset_portfolio(initial_cash)
