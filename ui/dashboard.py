"""대시보드 페이지"""
import streamlit as st
import plotly.graph_objects as go
from core.portfolio import Portfolio


def render(portfolio: Portfolio):
    snap = portfolio.get_snapshot()

    # ── 상단 자산 요약 ────────────────────────────────────────
    st.markdown("## 내 자산")
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "총자산",
            f"{snap['total_assets']:,.0f}원",
            delta=None,
        )
    with col2:
        pnl = snap["total_pnl"]
        pnl_pct = snap["total_pnl_pct"]
        st.metric(
            "평가손익",
            f"{pnl:+,.0f}원",
            delta=f"{pnl_pct:+.2f}%",
            delta_color="normal",
        )
    with col3:
        st.metric("예수금(현금)", f"{snap['cash']:,.0f}원")

    st.divider()

    # ── 보유 종목 요약 ────────────────────────────────────────
    holdings = snap["holdings"]
    if not holdings:
        st.info("보유 종목이 없습니다. 봇 설정에서 감시 종목을 추가하세요.")
        return

    st.markdown("### 보유 종목")
    for h in holdings:
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([3, 2, 2, 2])
            c1.markdown(f"**{h['name']}** `{h['ticker']}`")
            c2.markdown(f"현재가 **{h['current_price']:,.0f}원**")
            c3.markdown(f"평균가 {h['avg_price']:,.0f}원")
            color = "red" if h["pnl"] >= 0 else "blue"
            c4.markdown(
                f"<span style='color:{color};font-weight:bold'>"
                f"{h['pnl']:+,.0f}원 ({h['pnl_pct']:+.2f}%)</span>",
                unsafe_allow_html=True,
            )

    # ── 자산 구성 파이 차트 ────────────────────────────────────
    st.divider()
    st.markdown("### 자산 구성")
    labels = [h["name"] for h in holdings] + ["현금"]
    values = [h["eval_amount"] for h in holdings] + [snap["cash"]]
    fig = go.Figure(go.Pie(
        labels=labels, values=values, hole=0.55,
        textinfo="label+percent",
        marker=dict(line=dict(color="#ffffff", width=2)),
    ))
    fig.update_layout(
        height=320,
        margin=dict(t=10, b=10, l=10, r=10),
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)
