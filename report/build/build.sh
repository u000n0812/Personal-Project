#!/usr/bin/env bash
# 장별 Markdown을 하나로 묶어 HTML로 만든 뒤 PDF로 변환한다.
# 필요: pandoc, Node.js + playwright(Chromium), Pretendard 폰트(시스템 설치)
set -euo pipefail
cd "$(dirname "$0")/.."

OUT_HTML=build/report.html
OUT_PDF="반도체_생산관리_세부직무_분석.pdf"

pandoc chapters/*.md \
  --from markdown+task_lists \
  --to html5 --standalone \
  --toc --toc-depth=2 --number-sections \
  --css style.css \
  --metadata pagetitle="반도체 생산관리 세부직무 분석" \
  -o "$OUT_HTML"

node build/pdf.js "$OUT_HTML" "$OUT_PDF"
echo "완료: report/$OUT_PDF"
