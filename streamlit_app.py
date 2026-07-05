"""Streamlit 웹앱 — 상대 모멘텀 자산배분 백테스트.

Streamlit Cloud 배포 시 이 파일을 'Main file path'로 지정하세요.
"""
import os
import sys

# ── src 패키지를 확실히 import 하도록 저장소 루트를 경로에 추가 ──
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st

from src.data import download_prices
from src.metrics import compute_metrics, drawdown_series, yearly_returns
from src.strategy import run_backtest

st.set_page_config(page_title="상대 모멘텀 자산배분 백테스트", page_icon="📈", layout="wide")

st.title("📈 상대 모멘텀 자산배분 백테스트")
st.caption(
    "위험자산 3종(코스피·S&P500·금) 중 최근 N개월 수익률 1위에 올인, "
    "세 자산이 모두 마이너스면 방어자산(IEF·BIL) 중 모멘텀 높은 쪽으로 전환. 매월 말 리밸런싱."
)

# ──────────────────────────────── 사이드바(입력) ────────────────────────────────
with st.sidebar:
    st.header("⚙️ 설정")

    start = st.date_input("시작일", value=pd.to_datetime("2000-01-01")).strftime("%Y-%m-%d")
    use_today = st.checkbox("오늘까지", value=True)
    end = None if use_today else st.date_input("종료일", value=pd.to_datetime("today")).strftime("%Y-%m-%d")

    lookback = st.slider("모멘텀 기간(개월)", 1, 12, 3)
    threshold = st.number_input("방어 전환 임계값", value=0.0, step=0.01,
                                help="위험자산 최고 모멘텀이 이 값보다 작으면 방어자산으로 전환")
    commission = st.number_input("교체당 거래비용(%)", value=0.10, step=0.05) / 100.0

    st.divider()
    st.subheader("티커 (Yahoo Finance)")
    st.caption("2000년부터 받으려면 지수/선물 기본값 권장")
    kospi = st.text_input("코스피", "^KS11")
    sp500 = st.text_input("S&P500", "SPY")
    gold = st.text_input("금", "GC=F")
    ief = st.text_input("방어자산1 (IEF)", "IEF")
    bil = st.text_input("방어자산2 (BIL)", "BIL")

    run = st.button("🚀 백테스트 실행", type="primary", use_container_width=True)

risky_tk = {"KOSPI": kospi, "SP500": sp500, "GOLD": gold}
def_tk = {"IEF": ief, "BIL": bil}
tickers = {**risky_tk, **def_tk}


@st.cache_data(show_spinner="데이터 다운로드 중...", ttl=60 * 60)
def load_prices(tickers_items, start, end):
    return download_prices(dict(tickers_items), start=start, end=end)


def pct(x):
    return "—" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x*100:.2f}%"


# ──────────────────────────────── 실행 ────────────────────────────────
if not run:
    st.info("왼쪽 사이드바에서 설정을 확인하고 **백테스트 실행**을 누르세요.")
    st.stop()

try:
    prices = load_prices(tuple(tickers.items()), start, end)
except Exception as e:  # noqa: BLE001
    st.error(f"데이터 다운로드 실패: {e}")
    st.stop()

if prices.empty:
    st.error("받은 가격 데이터가 없습니다. 티커를 확인하세요.")
    st.stop()

risky = [a for a in risky_tk if a in prices.columns]
defensive = [a for a in def_tk if a in prices.columns]
st.success(
    f"데이터: {prices.index.min().date()} ~ {prices.index.max().date()} · "
    f"{prices.shape[0]}일 · 자산 {', '.join(prices.columns)}"
)

res = run_backtest(prices, risky=risky, defensive=defensive,
                   lookback=lookback, threshold=threshold, commission=commission)

m = compute_metrics(res["monthly_returns"], res["equity"])

# ── 현재 추천(가장 최근 신호) ──
latest_signal = res["signals"].dropna().iloc[-1]
latest_date = res["signals"].dropna().index[-1]
st.subheader(f"🎯 현재 추천 자산: **{latest_signal}**  \n<small>({latest_date.date()} 기준 신호)</small>",
             help="가장 최근 월말 모멘텀 기준으로 다음 달 보유 대상")

# ── KPI ──
c1, c2, c3, c4 = st.columns(4)
c1.metric("CAGR", pct(m.get("CAGR")))
c2.metric("MDD", pct(m.get("MDD")))
c3.metric("Sharpe", f"{m.get('Sharpe', float('nan')):.2f}")
c4.metric("최종 배수", f"{res['equity'].iloc[-1]:.2f}x")

# ── 자산곡선 ──
st.subheader("자산곡선 (Equity Curve)")
log_scale = st.checkbox("로그 스케일", value=True)
fig, ax = plt.subplots(figsize=(11, 5))
ax.plot(res["equity"].index, res["equity"].values, label="Strategy", color="black", lw=2.2)
for col in risky:
    bh = f"BH_{col}"
    if bh in res["benchmarks"]:
        ax.plot(res["benchmarks"].index, res["benchmarks"][bh].values, label=col, alpha=0.7)
if "EW_risky" in res["benchmarks"]:
    ax.plot(res["benchmarks"].index, res["benchmarks"]["EW_risky"].values,
            label="Equal-Weight", ls="--", alpha=0.6)
if log_scale:
    ax.set_yscale("log")
ax.set_ylabel("Growth of 1")
ax.legend()
ax.grid(True, alpha=0.3)
st.pyplot(fig)

# ── 낙폭 ──
st.subheader("낙폭 (Drawdown)")
dd = drawdown_series(res["equity"])
fig2, ax2 = plt.subplots(figsize=(11, 3))
ax2.fill_between(dd.index, dd.values * 100, 0, color="crimson", alpha=0.5)
ax2.set_ylabel("%")
ax2.grid(True, alpha=0.3)
st.pyplot(fig2)

# ── 성과 비교표 ──
st.subheader("전략 vs 벤치마크")
rows = [("Strategy", m)]
for col in res["benchmarks"].columns:
    eq = res["benchmarks"][col]
    rr = eq.pct_change(fill_method=None).fillna(0.0)
    rows.append((col, compute_metrics(rr, eq)))
table = pd.DataFrame(
    {
        name: {
            "CAGR": mm.get("CAGR"),
            "Volatility": mm.get("Volatility"),
            "MDD": mm.get("MDD"),
            "Sharpe": mm.get("Sharpe"),
            "Calmar": mm.get("Calmar"),
        }
        for name, mm in rows if mm
    }
).T
fmt = table.copy()
for c in ["CAGR", "Volatility", "MDD"]:
    fmt[c] = fmt[c].map(lambda v: pct(v))
for c in ["Sharpe", "Calmar"]:
    fmt[c] = fmt[c].map(lambda v: f"{v:.2f}")
st.dataframe(fmt, use_container_width=True)

# ── 연도별 수익률 ──
st.subheader("연도별 수익률")
yr = yearly_returns(res["monthly_returns"])
st.bar_chart(yr.rename("연수익률"))

# ── 보유 자산 추이 ──
with st.expander("월별 보유 자산 / 신호 보기"):
    detail = pd.DataFrame({
        "equity": res["equity"],
        "monthly_return": res["monthly_returns"],
        "held_asset": res["positions"],
        "signal": res["signals"],
    })
    st.dataframe(detail, use_container_width=True)
    st.download_button(
        "⬇️ 결과 CSV 다운로드",
        detail.to_csv(encoding="utf-8-sig").encode("utf-8-sig"),
        file_name="backtest_timeseries.csv",
        mime="text/csv",
    )

st.caption("⚠️ 참고용 백테스트입니다. 지수/선물/프록시 혼용·세금·환율 등으로 실제와 차이가 있으며 투자 권유가 아닙니다.")
