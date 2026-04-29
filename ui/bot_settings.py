"""봇 설정 및 수동 실행 페이지"""
import streamlit as st
from core.portfolio import Portfolio
from core.risk_manager import RiskManager
from broker.paper import PaperBroker, get_watchlist, set_watchlist
from strategies.sma_crossover import SMACrossoverStrategy
from strategies.rsi import RSIStrategy
from strategies.bollinger import BollingerStrategy
from data.fetcher import search_tickers, get_stock_name
from config import DEFAULT_INITIAL_CASH, STRATEGY_DEFAULTS


STRATEGY_CLASSES = {
    "sma_crossover": SMACrossoverStrategy,
    "rsi": RSIStrategy,
    "bollinger": BollingerStrategy,
}
STRATEGY_LABELS = {
    "sma_crossover": "SMA 이동평균 교차",
    "rsi": "RSI 과매수/과매도",
    "bollinger": "볼린저 밴드",
}


def render(portfolio: Portfolio):
    st.markdown("## 봇 설정")

    # ── 전략 선택 ─────────────────────────────────────────────
    st.markdown("### 트레이딩 전략")
    strategy_key = st.selectbox(
        "전략",
        list(STRATEGY_LABELS.keys()),
        format_func=lambda k: STRATEGY_LABELS[k],
    )

    params = {}
    if strategy_key == "sma_crossover":
        d = STRATEGY_DEFAULTS["sma_crossover"]
        params["short_window"] = st.slider("단기 이동평균 기간", 3, 20, d["short_window"])
        params["long_window"] = st.slider("장기 이동평균 기간", 10, 60, d["long_window"])
    elif strategy_key == "rsi":
        d = STRATEGY_DEFAULTS["rsi"]
        params["period"] = st.slider("RSI 기간", 7, 21, d["period"])
        params["oversold"] = st.slider("과매도 기준", 10, 40, d["oversold"])
        params["overbought"] = st.slider("과매수 기준", 60, 90, d["overbought"])
    else:
        d = STRATEGY_DEFAULTS["bollinger"]
        params["window"] = st.slider("볼린저 기간", 10, 30, d["window"])
        params["num_std"] = st.slider("표준편차 배수", 1.0, 3.0, float(d["num_std"]), step=0.1)

    st.divider()

    # ── 리스크 설정 ────────────────────────────────────────────
    st.markdown("### 리스크 관리")
    col1, col2 = st.columns(2)
    stop_loss = col1.number_input("손절 기준 (%)", min_value=1.0, max_value=30.0, value=5.0, step=0.5)
    take_profit = col2.number_input("익절 기준 (%)", min_value=1.0, max_value=50.0, value=10.0, step=0.5)

    st.divider()

    # ── 매수 금액 설정 ─────────────────────────────────────────
    st.markdown("### 주문 설정")
    order_amount = st.number_input("1회 매수 금액 (원)", min_value=100_000, max_value=5_000_000,
                                   value=500_000, step=100_000)
    max_position_pct = st.slider("종목당 최대 비중 (%)", 5, 50, 20)

    st.divider()

    # ── 감시 종목 ─────────────────────────────────────────────
    st.markdown("### 감시 종목")
    watchlist = get_watchlist()

    search = st.text_input("종목 추가 검색", placeholder="삼성전자 / 005930")
    if search:
        results = search_tickers(search)
        if not results.empty:
            opts = {f"{r['name']} ({r['ticker']})": r["ticker"] for _, r in results.iterrows()}
            sel = st.selectbox("추가할 종목", list(opts.keys()))
            if st.button("추가"):
                t = opts[sel]
                if t not in watchlist:
                    watchlist.append(t)
                    set_watchlist(watchlist)
                    st.success(f"{sel} 추가 완료")
                    st.rerun()

    if watchlist:
        st.markdown("**현재 감시 종목:**")
        for i, t in enumerate(watchlist):
            c1, c2 = st.columns([5, 1])
            c1.markdown(f"`{t}` {get_stock_name(t)}")
            if c2.button("삭제", key=f"del_{t}"):
                watchlist.remove(t)
                set_watchlist(watchlist)
                st.rerun()
    else:
        st.info("감시 종목을 추가하세요.")

    st.divider()

    # ── 수동 실행 ─────────────────────────────────────────────
    st.markdown("### 봇 실행")
    col_run, col_risk = st.columns(2)

    with col_run:
        if st.button("전략 신호 실행", type="primary", use_container_width=True):
            if not watchlist:
                st.warning("감시 종목을 먼저 추가하세요.")
            else:
                strategy = STRATEGY_CLASSES[strategy_key](**params)
                broker = PaperBroker(portfolio, strategy, order_amount, max_position_pct)
                with st.spinner("신호 분석 중..."):
                    results = broker.run_all(watchlist)
                st.markdown("**실행 결과:**")
                for ticker, msg in results.items():
                    name = get_stock_name(ticker)
                    st.write(f"- `{ticker}` {name}: {msg}")

    with col_risk:
        if st.button("손절/익절 체크", use_container_width=True):
            rm = RiskManager(stop_loss, take_profit)
            logs = rm.check_and_execute(portfolio)
            if logs:
                for log in logs:
                    st.warning(log)
            else:
                st.success("손절/익절 조건 미충족 — 보유 유지")

    st.divider()

    # ── 수동 주문 ─────────────────────────────────────────────
    st.markdown("### 수동 주문")
    with st.expander("직접 매수/매도"):
        m_ticker = st.text_input("종목코드", placeholder="005930")
        m_qty = st.number_input("수량", min_value=1, value=1)
        m_price = st.number_input("가격 (0 = 현재가)", min_value=0, value=0)
        c_buy, c_sell = st.columns(2)
        if c_buy.button("매수 실행"):
            from data.fetcher import get_current_price
            price = m_price if m_price > 0 else get_current_price(m_ticker)
            result = portfolio.execute_buy(m_ticker, m_qty, price, "manual")
            st.info(f"매수: {result}")
        if c_sell.button("매도 실행"):
            from data.fetcher import get_current_price
            price = m_price if m_price > 0 else get_current_price(m_ticker)
            result = portfolio.execute_sell(m_ticker, m_qty, price, "manual")
            st.info(f"매도: {result}")

    st.divider()

    # ── 포트폴리오 초기화 ──────────────────────────────────────
    st.markdown("### 포트폴리오 초기화")
    new_cash = st.number_input("초기 자금 (원)", min_value=1_000_000,
                               value=DEFAULT_INITIAL_CASH, step=1_000_000)
    if st.button("초기화 (모든 거래내역 삭제)", type="secondary"):
        portfolio.reset(new_cash)
        st.success(f"포트폴리오를 {new_cash:,.0f}원으로 초기화했습니다.")
        st.rerun()
