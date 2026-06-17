# Commodity Quant — 원자재 가격 추적 & 예측

원자재(에너지·귀금속·산업금속·농산물) 가격을 **퀀트(Quant) 기법**으로 추적하고
다음 거래일을 예측하는 알고리즘 프로젝트입니다. 여러 예측 모델을
**워크-포워드 백테스트**로 공정하게 비교하여, 어떤 모델이 실제로 예측력이 있는지
정량적으로 판단합니다.

## 핵심 특징

- **다중 자산군**: WTI/Brent/천연가스, 금/은, 구리, 옥수수/밀/대두 (config 에서 자유롭게 추가)
- **다중 모델 비교**:
  | 모델 | 종류 | 예측 대상 | 라이브러리 |
  |------|------|-----------|------------|
  | `naive` | 통계(기준선) | random-walk (수익률 0) | - |
  | `arima` | 통계 | 다음날 로그수익률 | statsmodels |
  | `garch` | 통계 | 다음날 **변동성** | arch |
  | `xgboost` | 머신러닝 | 다음날 로그수익률 | xgboost |
  | `lstm` | 딥러닝(선택) | 다음날 로그수익률 | torch |
- **3중 데이터 소스**: `yfinance`(온라인) / `csv`(로컬 파일) / `synthetic`(오프라인 합성)
- **누수 없는 백테스트**: 매 시점 과거 데이터만으로 학습/예측 (look-ahead bias 방지)
- **트레이딩 친화 지표**: RMSE/MAE 뿐 아니라 **방향 적중률(directional accuracy)**, 변동성은 QLIKE

## 설치

```bash
pip install -r requirements.txt
# LSTM 사용 시 추가:
# pip install torch
```

## 빠른 시작

```bash
# config.yaml 전체 심볼 실행 (기본 데이터 소스: synthetic — 네트워크 불필요)
python scripts/run_pipeline.py

# 특정 심볼만, 검증 구간 80일
python scripts/run_pipeline.py --symbols GC=F CL=F --test-size 80

# 온라인 데이터(yfinance)로 실행
python scripts/run_pipeline.py --source yfinance
```

실행 결과는 `outputs/` 에 저장됩니다:
- `backtest_summary.csv` — 심볼·모델별 성능 지표
- `next_day_forecast.csv` — 최우수 모델 기반 다음 거래일 예측
- `<symbol>.png` — 가격 + 누적 예측 수익률 비교 그래프

## 데이터 소스 설정

`config.yaml` 의 `data.source` 로 전환합니다.

```yaml
data:
  source: synthetic   # yfinance | csv | synthetic
```

- **yfinance**: Yahoo Finance 에서 자동 수집(+parquet 캐싱).
  > ⚠️ Claude Code 웹 실행 환경 등 **네트워크가 제한된 곳에서는 야후 호스트
  > (`query1.finance.yahoo.com`, `query2.finance.yahoo.com`)가 차단**될 수 있습니다.
  > 이 경우 환경의 네트워크 egress 허용 목록에 두 호스트를 추가하세요.
- **csv**: `data/<symbol>.csv` 파일을 사용 (예: `data/CL_F.csv`). 첫 열은 날짜, 이후 OHLCV.
- **synthetic**: 자산군 특성(추세·변동성·평균회귀·점프·계절성)을 반영한 합성 데이터를
  생성합니다. **네트워크 없이 전체 파이프라인을 즉시 실행/테스트** 할 때 사용합니다.

## 프로젝트 구조

```
src/commodity_quant/
├── config.py            # config.yaml 로딩
├── data/
│   ├── loader.py        # yfinance / csv / synthetic 통합 적재기
│   └── synthetic.py     # 오프라인 합성 가격 생성기
├── features/
│   └── technical.py     # 수익률·이동평균·RSI·MACD·변동성 등 기술적 피처
├── models/
│   ├── base.py          # 공통 예측기 인터페이스
│   ├── naive.py         # random-walk 기준선
│   ├── arima_model.py   # ARIMA
│   ├── garch_model.py   # GARCH(1,1) 변동성
│   ├── ml_model.py      # XGBoost
│   └── lstm_model.py    # LSTM (torch, 선택)
├── backtest/
│   ├── evaluator.py     # 워크-포워드 엔진
│   └── metrics.py       # 성능 지표 (방향 적중률, QLIKE 등)
└── pipeline.py          # 적재→피처→백테스트→비교→예측→그래프
```

## 방법론 메모

- 모델은 가격이 아니라 **로그수익률**을 예측합니다. 수익률은 정상성에 가까워
  통계 모델이 잘 작동하고, 모델 간 비교가 공정해집니다.
- `naive(random-walk)` 는 강력한 기준선입니다. 다른 모델이 이를 (특히
  **방향 적중률 50% 초과**로) 이기지 못하면 실질적 예측력이 없다는 신호입니다.
- 백테스트는 `refit_every` 주기로 모델을 재학습하여 속도와 정확도를 절충합니다.

## 테스트

```bash
python -m pytest tests/ -q
```

## 면책 조항

본 프로젝트는 **연구·교육용**입니다. 합성 데이터 결과는 실제 시장과 무관하며,
어떤 예측도 투자 수익을 보장하지 않습니다. 투자 판단의 근거로 사용하지 마세요.
