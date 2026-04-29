"""
한국투자증권 KIS OpenAPI 클라이언트
- 모의투자(paper) / 실투자(real) 모드 전환
- 토큰 자동 발급 및 캐싱
- REST: 현재가 조회, 주문 실행, 계좌 조회
"""
import os
import json
import time
import aiohttp
import asyncio
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# ── 엔드포인트 ───────────────────────────────────────────────
_ENDPOINTS = {
    "paper": {
        "base":     "https://openapivts.koreainvestment.com:29443",
        "ws":       "ws://ops.koreainvestment.com:31000",
        "tr_buy":   "VTTC0802U",
        "tr_sell":  "VTTC0801U",
        "tr_price": "FHKST01010100",
        "tr_bal":   "VTTC8434R",
    },
    "real": {
        "base":     "https://openapi.koreainvestment.com:9443",
        "ws":       "ws://ops.koreainvestment.com:21000",
        "tr_buy":   "TTTC0802U",
        "tr_sell":  "TTTC0801U",
        "tr_price": "FHKST01010100",
        "tr_bal":   "TTTC8434R",
    },
}


class KISClient:
    def __init__(self):
        self.app_key    = os.getenv("KIS_APP_KEY", "")
        self.app_secret = os.getenv("KIS_APP_SECRET", "")
        self.account_no = os.getenv("KIS_ACCOUNT_NO", "")
        self.mode       = os.getenv("TRADING_MODE", "paper")
        self._ep        = _ENDPOINTS[self.mode]
        self._token: str = ""
        self._token_exp: float = 0.0

    # ── 인증 ────────────────────────────────────────────────
    async def _ensure_token(self, session: aiohttp.ClientSession):
        if time.time() < self._token_exp - 60:
            return
        url = f"{self._ep['base']}/oauth2/tokenP"
        body = {
            "grant_type": "client_credentials",
            "appkey":     self.app_key,
            "appsecret":  self.app_secret,
        }
        async with session.post(url, json=body) as resp:
            data = await resp.json()
        self._token     = data["access_token"]
        self._token_exp = time.time() + int(data.get("expires_in", 86400))

    def _headers(self, tr_id: str, extra: dict | None = None) -> dict:
        h = {
            "Content-Type":  "application/json",
            "authorization": f"Bearer {self._token}",
            "appkey":        self.app_key,
            "appsecret":     self.app_secret,
            "tr_id":         tr_id,
        }
        if extra:
            h.update(extra)
        return h

    # ── 현재가 조회 ─────────────────────────────────────────
    async def get_price(self, ticker: str) -> dict:
        """현재가, 전일 대비, 거래량 반환"""
        async with aiohttp.ClientSession() as s:
            await self._ensure_token(s)
            url    = f"{self._ep['base']}/uapi/domestic-stock/v1/quotations/inquire-price"
            params = {"fid_cond_mrkt_div_code": "J", "fid_input_iscd": ticker}
            async with s.get(url, headers=self._headers(self._ep["tr_price"]), params=params) as r:
                data = await r.json()

        out = data.get("output", {})
        return {
            "ticker":      ticker,
            "price":       int(out.get("stck_prpr", 0)),
            "change_pct":  float(out.get("prdy_ctrt", 0)),
            "volume":      int(out.get("acml_vol", 0)),
            "high":        int(out.get("stck_hgpr", 0)),
            "low":         int(out.get("stck_lwpr", 0)),
        }

    # ── 주문 실행 ────────────────────────────────────────────
    async def order(self, ticker: str, side: str, quantity: int, price: int = 0) -> dict:
        """
        side: "BUY" | "SELL"
        price=0 → 시장가
        """
        acct, prod = self.account_no.split("-")
        tr_id = self._ep["tr_buy"] if side == "BUY" else self._ep["tr_sell"]
        body = {
            "CANO":                acct,
            "ACNT_PRDT_CD":        prod,
            "PDNO":                ticker,
            "ORD_DVSN":            "01" if price == 0 else "00",  # 01=시장가 00=지정가
            "ORD_QTY":             str(quantity),
            "ORD_UNPR":            "0" if price == 0 else str(price),
        }
        async with aiohttp.ClientSession() as s:
            await self._ensure_token(s)
            url = f"{self._ep['base']}/uapi/domestic-stock/v1/trading/order-cash"
            async with s.post(url, headers=self._headers(tr_id, {"custtype": "P"}), json=body) as r:
                data = await r.json()

        success = data.get("rt_cd") == "0"
        return {
            "success": success,
            "order_no": data.get("output", {}).get("ODNO", ""),
            "message":  data.get("msg1", ""),
        }

    # ── 계좌 조회 ────────────────────────────────────────────
    async def get_balance(self) -> dict:
        """예수금 및 보유 종목 조회"""
        acct, prod = self.account_no.split("-")
        params = {
            "CANO":           acct,
            "ACNT_PRDT_CD":   prod,
            "AFHR_FLPR_YN":   "N",
            "OFL_YN":         "",
            "INQR_DVSN":      "02",
            "UNPR_DVSN":      "01",
            "FUND_STTL_ICLD_YN": "N",
            "FNCG_AMT_AUTO_RDPT_YN": "N",
            "PRCS_DVSN":      "01",
            "CTX_AREA_FK100": "",
            "CTX_AREA_NK100": "",
        }
        async with aiohttp.ClientSession() as s:
            await self._ensure_token(s)
            url = f"{self._ep['base']}/uapi/domestic-stock/v1/trading/inquire-balance"
            async with s.get(url, headers=self._headers(self._ep["tr_bal"]), params=params) as r:
                data = await r.json()

        out2 = data.get("output2", [{}])[0]
        holdings = []
        for item in data.get("output1", []):
            qty = int(item.get("hldg_qty", 0))
            if qty > 0:
                holdings.append({
                    "ticker":    item.get("pdno"),
                    "name":      item.get("prdt_name"),
                    "quantity":  qty,
                    "avg_price": float(item.get("pchs_avg_pric", 0)),
                    "cur_price": int(item.get("prpr", 0)),
                    "pnl_pct":   float(item.get("evlu_pfls_rt", 0)),
                })
        return {
            "cash":     int(out2.get("prvs_rcdl_excc_amt", 0)),
            "holdings": holdings,
        }

    # ── WebSocket 승인키 발급 ────────────────────────────────
    async def get_ws_approval_key(self) -> str:
        url  = f"{self._ep['base']}/oauth2/Approval"
        body = {"grant_type": "client_credentials", "appkey": self.app_key, "secretkey": self.app_secret}
        async with aiohttp.ClientSession() as s:
            async with s.post(url, json=body) as r:
                data = await r.json()
        return data.get("approval_key", "")

    @property
    def ws_url(self) -> str:
        return self._ep["ws"]

    def is_configured(self) -> bool:
        return bool(self.app_key and self.app_secret and self.account_no)
