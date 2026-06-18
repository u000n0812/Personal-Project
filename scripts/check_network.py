#!/usr/bin/env python3
"""yfinance(야후 파이낸스) 연결 점검 도구.

실행 환경의 네트워크 egress 정책 때문에 야후 호스트가 막혀 있으면 실데이터를
받을 수 없다. 이 스크립트는 어떤 호스트가 막혀 있는지 진단하고, 허용해야 할
호스트 목록과 다음 단계를 안내한다.

    python scripts/check_network.py
"""
from __future__ import annotations

import sys
import urllib.request

# yfinance 가 실제로 접근하는 핵심 호스트들
YAHOO_HOSTS = [
    "https://query1.finance.yahoo.com/v8/finance/chart/GC=F",
    "https://query2.finance.yahoo.com/v8/finance/chart/GC=F",
    "https://finance.yahoo.com",
    "https://fc.yahoo.com",
]

ALLOWLIST = [
    "query1.finance.yahoo.com",
    "query2.finance.yahoo.com",
    "finance.yahoo.com",
    "fc.yahoo.com",
]


def _probe(url: str, timeout: int = 8) -> tuple[bool, str]:
    try:
        r = urllib.request.urlopen(url, timeout=timeout)
        return True, f"HTTP {r.status}"
    except urllib.error.HTTPError as e:
        # egress 프록시가 차단할 때 403 을 돌려준다 → 403 은 차단으로 간주
        blocked = e.code == 403
        return (not blocked), f"HTTP {e.code}{' (egress 차단)' if blocked else ''}"
    except Exception as e:  # DNS/타임아웃 등
        return False, f"{type(e).__name__}: {str(e)[:60]}"


def main() -> int:
    print("=== 외부 네트워크 연결 점검 ===\n")
    reachable = 0
    for url in YAHOO_HOSTS:
        ok, msg = _probe(url)
        host = url.split("/")[2]
        print(f"  [{'OK ' if ok else 'X  '}] {host:32s} {msg}")
        reachable += ok

    print()
    # 실제 yfinance 다운로드 시도
    yf_ok = False
    try:
        import yfinance as yf

        df = yf.download("GC=F", period="5d", progress=False, auto_adjust=True)
        yf_ok = df is not None and not df.empty
        print(f"yfinance 실데이터 테스트(GC=F): {'성공' if yf_ok else '실패'} (rows={0 if df is None else len(df)})")
    except Exception as e:
        print(f"yfinance 테스트 실패: {type(e).__name__}: {str(e)[:80]}")

    print("\n" + "=" * 60)
    if yf_ok:
        print("✅ yfinance 연결 정상! 다음으로 실행하세요:")
        print("     python scripts/run_gold_strategy.py --source yfinance")
        return 0

    print("❌ yfinance 로 실데이터를 받을 수 없습니다.\n")
    print("이 환경의 네트워크 egress 정책이 야후 호스트를 차단하고 있습니다.")
    print("코드 문제가 아니라 *환경 설정* 문제입니다. 해결 방법:\n")
    print(" [1] Claude Code on the web 환경의 네트워크 설정에서 아래 호스트를 허용:")
    for h in ALLOWLIST:
        print(f"       - {h}")
    print("     문서: https://code.claude.com/docs/en/claude-code-on-the-web\n")
    print(" [2] 네트워크를 못 여는 경우, 데이터를 직접 받아 CSV 로 사용:")
    print("       data/GC_F.csv, data/_TNX.csv, data/DX-Y.NYB.csv (Date,Open,High,Low,Close,Volume)")
    print("       config.yaml 의 data.source: csv 로 변경 후 실행\n")
    print(" [3] 우선 오프라인 데모(합성 데이터)로 로직 검증:")
    print("       python scripts/run_gold_strategy.py   # data.source: synthetic")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
