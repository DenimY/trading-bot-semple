# AI 에이전트 기반 한국 주식 트레이딩 봇

Claude AI를 사용한 실시간 한국 주식 자동매매 시스템입니다.

## 프로젝트 소개

- **AI 에이전트**: Claude Haiku(빠른 판단) + Sonnet(정확한 판단) 듀얼 티어
- **실시간 데이터**: KIS WebSocket 또는 pykrx 시세 수신
- **자동 매매**: RSI, SMA, 볼린저 밴드 기반 AI 판단
- **리스크 관리**: 손절/익절 자동 실행
- **실시간 대시보드**: FastAPI + WebSocket + TradingView 차트
- **모의투자**: 안전하게 테스트 후 실투자 전환 가능

## 빠른 시작

### 1. 설치
```bash
git clone git@github.com:DenimY/trading-bot-semple.git
cd trading-bot-semple
pip3 install -r requirements.txt
```

### 2. 환경 설정
```bash
cp .env.example .env
# .env 파일에 ANTHROPIC_API_KEY 입력 (필수)
# KIS API 키는 선택 (없으면 pykrx 자동 사용)
```

### 3. 실행
```bash
# 실시간 대시보드 (추천)
python3 server.py
# → http://localhost:8006 접속

# 또는 Streamlit UI
streamlit run app.py
# → http://localhost:8501 접속
```

## 주요 기능

| 기능 | 설명 |
|------|------|
| **AI 에이전트** | Claude Haiku/Sonnet으로 매매 결정 |
| **실시간 시세** | KIS API WebSocket 또는 pykrx |
| **자동 주문** | BUY/SELL 자동 실행 |
| **손절/익절** | 설정 기준 도달 시 자동 매도 |
| **대시보드** | 실시간 차트 및 AI 판단 로그 |
| **모의투자** | 1천만원 가상자금으로 테스트 |

## 필요한 API 키

### Anthropic Claude API (필수)
- https://console.anthropic.com 에서 발급
- `.env`에 `ANTHROPIC_API_KEY` 입력

### 한국투자증권 KIS API (선택)
- https://apiportal.koreainvestment.com 가입
- 앱 등록 후 키 발급
- 모의투자 신청
- 미설정 시 pykrx로 자동 사용

## 프로젝트 구조

```
trading-bot-semple/
├── server.py              # FastAPI 서버
├── scheduler.py           # 백그라운드 에이전트
├── app.py                 # Streamlit UI
├── market_stream.py       # 실시간 시세
├── core/
│   ├── agent_engine.py    # AI 에이전트
│   ├── portfolio.py       # 포트폴리오 관리
│   ├── risk_manager.py    # 손절/익절
│   └── context_builder.py # AI 컨텍스트
├── broker/
│   └── kis_client.py      # 증권사 API
├── strategies/
│   ├── sma_crossover.py   # SMA 교차
│   ├── rsi.py             # RSI 지표
│   └── bollinger.py       # 볼린저 밴드
└── frontend/
    └── index.html         # 실시간 대시보드
```

## 라이센스

**Proprietary License** - 상세 내용은 [LICENSE](LICENSE) 파일 참고

주요 내용:
- ❌ 무단 배포, 판매, 수정 금지
- ❌ 상업적 사용 금지
- ✅ 출처 명시 필수
- ✅ 소유자 명시 필수

## 주의사항

- 모의투자로 충분히 검증 후 실투자 시작
- AI 판단의 오류 가능성 - 손실은 전적으로 운용자 책임
- 보안: `.env` 파일 절대 커밋 금지
- 한국 주식 거래시간(09:00~15:30) 외에는 자동 비활성화

## 다음 단계

1. 모의투자로 1~2주 테스트
2. 성과 검증 및 파라미터 최적화
3. KIS API 실투자 키 발급
4. 실투자 모드 전환

## 문서

- [docs/ai-agent-architecture.md](docs/ai-agent-architecture.md) - 아키텍처 설명
- [TODO.md](TODO.md) - 개발 로드맵

---

**Made with Claude AI** © 2026
