# Gold Quant — 실질금리 + 달러 신뢰로 금을 사고파는 알고리즘

**순수 파이썬** 프로젝트입니다. 도커·서버·복잡한 설정 없이 `python main.py` 한 줄로 실행됩니다.

## 무엇을 하나요?

금 가격을 움직이는 두 가지 매크로 요인을 매일 점수화해서 **매수 / 매도 / 관망**을 결정합니다.

| 신호 | 데이터 (yfinance) | 논리 |
|------|------------------|------|
| **① 실질금리** | `^TNX` (미국 10년물 금리) | 금은 이자가 없는 자산 → 실질금리가 **낮아질수록** 금 매력 ↑ → 매수 |
| **② 달러 신뢰** | `DX-Y.NYB` (달러 인덱스) | 금은 달러의 대체 안전자산 → 달러 신뢰가 **약해질수록**(달러 약세) 금 수요 ↑ → 매수 |

각 요인을 *수준*과 *모멘텀*의 z-score로 표준화하고 가중 합산해 **합성 점수** 하나를 만듭니다.
점수가 `+0.4`를 넘으면 매수, `-0.4` 아래면 매도(숏), 그 사이면 관망합니다.
그리고 이 규칙대로 과거에 매매했다면 얼마를 벌었을지 **백테스트**로 검증합니다
(미래 정보 사용 금지, 거래비용 반영, Buy & Hold와 비교).

## 설치 & 실행 (Windows PowerShell 기준)

```powershell
# 1. 코드 받기 (처음 한 번만)
git clone https://github.com/u000n0812/Personal-Project.git
cd Personal-Project

# 2. 라이브러리 설치 (처음 한 번만)
python -m pip install -r requirements.txt

# 3. 실행
python main.py
```

> 💡 `python`이 인식되지 않으면 `py main.py`, `py -m pip install -r requirements.txt`처럼
> `python` 대신 `py`를 쓰세요. 둘 다 안 되면 [python.org](https://www.python.org/downloads/)에서
> 파이썬 설치 시 **"Add python.exe to PATH"를 반드시 체크**하세요.

Mac/Linux도 동일하게 `python3 main.py`로 실행됩니다.

### 옵션

```powershell
python main.py --start 2020-01-01   # 백테스트 시작일 변경
python main.py --no-short           # 숏 금지 (매도 신호가 나오면 그냥 현금 보유)
python main.py --cost-bps 3         # 거래비용을 3bp로 (기본 1bp)
python main.py --offline            # 인터넷 없이 데모 데이터로 실행
```

## 실행하면 나오는 것

```
=== 백테스트 성과 ===
  전략       | 연수익 +18.35% | 변동성 11.50% | Sharpe 1.60 | 최대낙폭 -20.35% | ...
  Buy&Hold   | 연수익  +1.05% | 변동성 13.39% | Sharpe 0.08 | 최대낙폭 -44.32% | ...

=== 오늘의 매매 권고 ===
  실질금리  0.857% → 신호 -0.64
  달러 인덱스 91.18 → 신호 -0.26
  합성 점수 -0.52  (임계값 ±0.4)
  >>> 결정 : 매도 (SELL/SHORT)
```

- `outputs/gold_report.png` — 금 가격+매매시점, 두 신호, 자산곡선 차트
- `outputs/backtest_result.csv` — 일별 신호·포지션·손익 전체 데이터

## 파일 구성 (전부 5개)

```
main.py                  실행 진입점 — 이것만 실행하면 됨
gold_quant/
├── data.py              yfinance 다운로드 (+오프라인 데모 폴백)
├── signals.py           ①실질금리 ②달러 → 매수/매도 점수 (파라미터도 여기)
├── backtest.py          과거 성과 검증 (Sharpe, 최대낙폭, 승률...)
└── charts.py            결과 차트 저장
tests/test_gold_quant.py 로직 검증 테스트 (python -m pytest tests/ -q)
```

전략을 튜닝하고 싶으면 `gold_quant/signals.py` 맨 위의 `Params` 숫자들만 바꾸면 됩니다.

## 자주 묻는 질문

**Q. 인터넷이 막힌 환경에서 "데모 데이터로 실행" 경고가 떠요.**
야후 파이낸스 접속이 차단된 환경(회사망, 샌드박스 등)입니다. 코드 문제가 아니며,
일반 인터넷이 되는 PC에서 실행하면 자동으로 실데이터를 받습니다.

**Q. 실질금리가 아니라 명목금리(^TNX) 아닌가요?**
맞습니다. yfinance에는 실질금리(TIPS) 시계열이 없어 10년물 명목금리를 프록시로 씁니다.
신호가 z-score(상대 변화) 기반이라 실용적으로 잘 작동하지만, 정밀하게 하려면
FRED의 `DFII10`을 받아 `data.py`에서 교체할 수 있습니다.

## ⚠️ 면책

연구·교육용 프로젝트입니다. 백테스트 성과(특히 데모 데이터)는 미래 수익을 보장하지
않으며, 실제 투자 판단의 근거로 사용하지 마세요.
