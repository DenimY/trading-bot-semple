"""리스크 관리: 손절/익절 자동 체크"""
from core.portfolio import Portfolio
from data.fetcher import get_current_price


class RiskManager:
    def __init__(self, stop_loss_pct: float = 5.0, take_profit_pct: float = 10.0):
        self.stop_loss_pct = stop_loss_pct       # 손절 기준 (%)
        self.take_profit_pct = take_profit_pct   # 익절 기준 (%)

    def check_and_execute(self, portfolio: Portfolio) -> list[str]:
        """
        보유 종목 순회 → 손절/익절 조건 달성 시 전량 매도.
        반환: 실행된 액션 로그 리스트
        """
        logs = []
        for h in portfolio.get_holdings():
            cur = get_current_price(h["ticker"])
            if cur <= 0:
                continue
            pnl_pct = (cur - h["avg_price"]) / h["avg_price"] * 100

            if pnl_pct <= -self.stop_loss_pct:
                msg = portfolio.execute_sell(h["ticker"], h["quantity"], cur, strategy="stop_loss")
                if msg == "OK":
                    logs.append(f"[손절] {h['name']}({h['ticker']}) {pnl_pct:.1f}% → 전량 매도 @ {cur:,.0f}원")

            elif pnl_pct >= self.take_profit_pct:
                msg = portfolio.execute_sell(h["ticker"], h["quantity"], cur, strategy="take_profit")
                if msg == "OK":
                    logs.append(f"[익절] {h['name']}({h['ticker']}) +{pnl_pct:.1f}% → 전량 매도 @ {cur:,.0f}원")

        return logs
