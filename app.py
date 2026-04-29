"""한국 주식 트레이딩 봇 - 메인 앱"""
import streamlit as st
from data.storage import init_db
from core.portfolio import Portfolio
from ui import dashboard, chart_view, trade_history, bot_settings

st.set_page_config(
    page_title="트레이딩 봇",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# CSS: 토스 스타일 카드 느낌
st.markdown("""
<style>
    [data-testid="stAppViewContainer"] { background-color: #f8f9fa; }
    [data-testid="stSidebar"] { background-color: #1b1e27; }
    [data-testid="stSidebar"] * { color: #e8eaf0 !important; }
    .stMetric { background: white; border-radius: 12px; padding: 16px; box-shadow: 0 1px 6px rgba(0,0,0,0.06); }
    div[data-testid="metric-container"] { background: white; border-radius: 12px; padding: 16px; box-shadow: 0 1px 6px rgba(0,0,0,0.06); }
    [data-testid="stContainer"] { background: white; border-radius: 12px; }
    h2, h3 { font-weight: 700; }
</style>
""", unsafe_allow_html=True)

# DB 초기화
init_db()

# 포트폴리오 싱글턴
portfolio = Portfolio()

# ── 사이드바 네비게이션 ───────────────────────────────────────
with st.sidebar:
    st.markdown("# 📈 트레이딩 봇")
    st.markdown("**모의투자 모드**")
    st.divider()

    page = st.radio(
        "메뉴",
        ["대시보드", "차트 분석", "거래 내역", "봇 설정"],
        label_visibility="collapsed",
    )

    st.divider()
    snap = portfolio.get_snapshot()
    st.markdown(f"**총자산** {snap['total_assets']:,.0f}원")
    pnl = snap["total_pnl"]
    color = "red" if pnl >= 0 else "blue"
    st.markdown(
        f"<span style='color:{color}'>평가손익 {pnl:+,.0f}원</span>",
        unsafe_allow_html=True,
    )
    st.markdown(f"예수금 {snap['cash']:,.0f}원")

# ── 페이지 라우팅 ─────────────────────────────────────────────
if page == "대시보드":
    dashboard.render(portfolio)
elif page == "차트 분석":
    chart_view.render()
elif page == "거래 내역":
    trade_history.render()
elif page == "봇 설정":
    bot_settings.render(portfolio)
