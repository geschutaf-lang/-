# 상대 모멘텀 자산 배분 백테스트 (Asset Rotation Backtest)

한국주식(코스피 ETF) · 미국 S&P500 ETF · 금(Gold) 세 위험자산 중
**최근 3개월 수익률이 가장 높은 1종에 올인**하고,
세 자산이 **모두 마이너스이면** 방어자산(IEF · BIL) 중 3개월 수익률이 높은 쪽으로
갈아타는 상대 모멘텀 전략을 백테스트합니다. (매월 말 리밸런싱, 2000-01-01 시작)

## 전략 규칙

1. 매월 말, 위험자산 3종의 최근 `lookback_months`(기본 3)개월 수익률을 계산
2. 최고 모멘텀이 `threshold`(기본 0) 이상 → 해당 **위험자산**에 다음 달 100% 투자
3. 세 위험자산이 모두 마이너스 → **방어자산**(IEF / BIL) 중 모멘텀이 높은 쪽에 100% 투자
4. 방어자산 데이터가 없는 구간(예: BIL 상장 이전)에는 **현금**(수익률 0%) 보유
5. 신호는 t월 말 데이터로 결정하고 수익은 t+1월에 실현 → **미래참조(look-ahead) 없음**

## 설치

```bash
git clone <이 저장소 URL>
cd asset-rotation-backtest

python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

## 실행 방법 1: 웹앱 (Streamlit) — 권장

로컬에서:

```bash
streamlit run streamlit_app.py
```

### Streamlit Cloud 배포

1. 이 저장소를 GitHub에 push
2. https://share.streamlit.io 에서 **New app** → 저장소 선택
3. **Main file path** 를 반드시 `streamlit_app.py` 로 지정 (⚠️ `run_backtest.py` 아님)
4. Deploy

> Streamlit Cloud는 사내 프록시가 없어 `yfinance` 데이터 다운로드가 정상 동작합니다.
> (로컬 회사망에서 나던 SSL 인증서 오류가 클라우드에선 발생하지 않습니다.)

## 실행 방법 2: 커맨드라인 (CLI)

```bash
python run_backtest.py                 # config.yaml 사용
python run_backtest.py --config my.yaml # 다른 설정 파일
python run_backtest.py --no-plots       # 차트 저장 생략
```

실행하면 콘솔에 성과 지표·벤치마크·연도별 수익률이 출력되고,
`results/` 폴더에 아래가 저장됩니다.

- `backtest_timeseries.csv` — 자산곡선 / 월수익 / 매월 보유자산·신호
- `metrics.csv` — 핵심 성과 지표
- `yearly_returns.csv` — 연도별 수익률
- `equity_curve.png`, `drawdown.png`, `positions.png` — 차트

## 설정 (`config.yaml`)

```yaml
backtest:
  start: "2000-01-01"
  end: null            # null = 오늘까지
  lookback_months: 3   # 모멘텀 기간
  threshold: 0.0       # 최고 모멘텀 < threshold 면 방어자산으로 전환
  commission: 0.001    # 종목 교체당 거래비용 (0.1%)

assets:
  risky:
    KOSPI: "^KS11"     # 코스피 지수 (ETF 대안 069500.KS 는 2002~)
    SP500: "SPY"       # 1993~
    GOLD:  "GC=F"      # 금 선물 2000~ (ETF 대안 GLD 2004~)
  defensive:
    IEF: "IEF"         # 7-10년 미국채 ETF 2002~
    BIL: "BIL"         # 1-3개월 T-Bill ETF 2007~
```

### 티커와 데이터 기간에 대한 참고

`2000-01-01`부터 돌리기 위해 기본 티커는 **지수/선물**을 사용합니다.
실제 ETF는 상장일 이후만 데이터가 있으니 목적에 맞게 바꿔 쓰세요.

| 자산 | 기본값 | 실제 ETF | 장기 프록시(2000년 이전) |
|---|---|---|---|
| 코스피 | `^KS11` (지수) | `069500.KS` (KODEX200, 2002~) | — |
| S&P500 | `SPY` (1993~) | `SPY` / `VOO` | `^GSPC` |
| 금 | `GC=F` (선물) | `GLD`(2004~) / `IAU`(2005~) | — |
| 미국 중기채 | `IEF` (2002~) | `IEF` | `VFITX` (1991~) |
| 초단기채/현금 | `BIL` (2007~) | `BIL` | `VFISX` (1991~) |

> IEF/BIL은 각각 2002/2007년 상장이라 그 이전 방어 구간에는 현금(0%)을 보유합니다.
> 방어자산까지 2000년부터 채우려면 `config.yaml`에서 IEF→`VFITX`, BIL→`VFISX`로 교체하세요.

## 테스트

전략 로직은 네트워크 없이 합성 데이터로 검증합니다.

```bash
pip install pytest
pytest -q
```

## 프로젝트 구조

```
asset-rotation-backtest/
├── streamlit_app.py        # 웹앱 진입점 (Streamlit Cloud 메인 파일)
├── run_backtest.py         # CLI 진입점 (설정 로드 → 다운로드 → 백테스트 → 출력/저장)
├── config.yaml             # 전략/티커/기간 설정
├── requirements.txt
├── src/
│   ├── data.py             # yfinance 가격 다운로드
│   ├── strategy.py         # 신호 생성 + 백테스트 엔진
│   ├── metrics.py          # CAGR·MDD·Sharpe·Calmar 등 지표
│   └── plotting.py         # 자산곡선·낙폭·보유자산 차트
├── tests/
│   └── test_strategy.py    # 단위 테스트(합성 데이터)
└── .github/workflows/ci.yml
```

## 알려진 이슈 / 주의

- **SSL 인증서 오류(사내 프록시/백신 환경)**: `yfinance`가
  `curl: (60) SSL certificate problem: self signed certificate` 오류를 내면,
  회사 네트워크의 HTTPS 검사 때문입니다. 개인 네트워크에서 실행하거나,
  회사 루트 인증서를 `CURL_CA_BUNDLE` / `SSL_CERT_FILE` 환경변수로 지정하세요.
- **데이터는 참고용**: 지수/선물/프록시 혼용, 배당·세금·환율 처리 등으로
  실제 투자 성과와 차이가 있을 수 있습니다. 투자 판단의 근거로 삼지 마세요.
- **월말 기준 리밸런싱**: 신호와 체결 시점을 월말로 단순화했습니다.

## 라이선스

MIT
