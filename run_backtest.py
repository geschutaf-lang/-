#!/usr/bin/env python
"""자산 배분(상대 모멘텀) 백테스트 실행 스크립트.

사용법:
    python run_backtest.py                 # config.yaml 사용
    python run_backtest.py --config my.yaml
    python run_backtest.py --no-plots
"""
from __future__ import annotations

import argparse
import os

import pandas as pd
import yaml

from src.data import download_prices
from src.metrics import compute_metrics, format_metrics, yearly_returns
from src.strategy import run_backtest


def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def main() -> None:
    parser = argparse.ArgumentParser(description="상대 모멘텀 자산 배분 백테스트")
    parser.add_argument("--config", default="config.yaml", help="설정 파일 경로")
    parser.add_argument("--no-plots", action="store_true", help="차트 저장 건너뛰기")
    args = parser.parse_args()

    cfg = load_config(args.config)
    bt = cfg["backtest"]
    assets = cfg["assets"]
    out = cfg.get("output", {})

    tickers = {**assets["risky"], **assets["defensive"]}
    risky = list(assets["risky"].keys())
    defensive = list(assets["defensive"].keys())

    print("=" * 60)
    print(" 상대 모멘텀 자산 배분 백테스트")
    print("=" * 60)
    print(f" 기간       : {bt['start']} ~ {bt['end'] or '현재'}")
    print(f" 모멘텀     : 최근 {bt['lookback_months']}개월 수익률")
    print(f" 위험자산   : {', '.join(f'{k}({v})' for k, v in assets['risky'].items())}")
    print(f" 방어자산   : {', '.join(f'{k}({v})' for k, v in assets['defensive'].items())}")
    print(f" 거래비용   : {bt['commission']*100:.2f}% / 교체")
    print("-" * 60)
    print(" 데이터 다운로드 중...")

    prices = download_prices(tickers, start=bt["start"], end=bt["end"])
    print(f" 받은 데이터: {prices.shape[0]}일 x {prices.shape[1]}종목")
    print(f" 데이터 시작: {prices.index[0].date()}  ({', '.join(prices.columns)})")

    # 실제 존재하는 자산만 신호에 사용
    risky = [a for a in risky if a in prices.columns]
    defensive = [a for a in defensive if a in prices.columns]

    result = run_backtest(
        prices,
        risky=risky,
        defensive=defensive,
        lookback=bt["lookback_months"],
        threshold=bt.get("threshold", 0.0),
        commission=bt.get("commission", 0.0),
        rule=bt.get("rebalance", "ME"),
    )

    # ---- 성과 요약 ----
    m = compute_metrics(result["monthly_returns"], result["equity"])
    print("\n" + "=" * 60)
    print(" [전략] 성과 지표")
    print("=" * 60)
    print(format_metrics(m))

    # 벤치마크 비교
    print("\n" + "-" * 60)
    print(" 벤치마크 비교 (CAGR / MDD / Sharpe)")
    print("-" * 60)
    bench_ret = result["asset_returns"]
    rows = []
    strat_m = compute_metrics(result["monthly_returns"], result["equity"])
    rows.append(("Strategy", strat_m))
    for col in result["benchmarks"].columns:
        eq = result["benchmarks"][col]
        rr = eq.pct_change(fill_method=None).fillna(0.0)
        rows.append((col, compute_metrics(rr, eq)))
    print(f"  {'name':<16}{'CAGR':>9}{'MDD':>9}{'Sharpe':>9}")
    for name, mm in rows:
        if mm:
            print(f"  {name:<16}{mm['CAGR']*100:>8.2f}%{mm['MDD']*100:>8.2f}%{mm['Sharpe']:>9.2f}")

    # 연도별 수익률
    yr = yearly_returns(result["monthly_returns"])
    print("\n" + "-" * 60)
    print(" 연도별 수익률")
    print("-" * 60)
    for year, val in yr.items():
        bar = "#" * int(max(0, val) * 40)
        print(f"  {year}: {val*100:7.2f}%  {bar}")

    # ---- 결과 저장 ----
    out_dir = out.get("dir", "results")
    os.makedirs(out_dir, exist_ok=True)

    summary = pd.DataFrame(
        {
            "equity": result["equity"],
            "monthly_return": result["monthly_returns"],
            "held_asset": result["positions"],
            "signal": result["signals"],
        }
    )
    summary.to_csv(f"{out_dir}/backtest_timeseries.csv", encoding="utf-8-sig")
    pd.Series(m).to_csv(f"{out_dir}/metrics.csv", encoding="utf-8-sig")
    yr.to_csv(f"{out_dir}/yearly_returns.csv", encoding="utf-8-sig")
    print(f"\n 결과 CSV 저장: {out_dir}/")

    if out.get("save_plots", True) and not args.no_plots:
        try:
            from src.plotting import plot_results

            paths = plot_results(result, risky, out_dir)
            print(" 차트 저장:", ", ".join(paths))
        except Exception as e:  # noqa: BLE001
            print(f" [경고] 차트 저장 실패: {e}")

    print("\n 완료.")


if __name__ == "__main__":
    main()
