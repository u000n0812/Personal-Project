#!/usr/bin/env bash
# 면접 연습 문제집을 PDF로 변환한다. 스타일과 변환기는 report/build 것을 함께 쓴다.
set -euo pipefail
cd "$(dirname "$0")"

pandoc practice.md \
  --from markdown \
  --to html5 --standalone \
  --toc --toc-depth=2 --number-sections \
  --css ../report/build/style.css \
  --metadata pagetitle="SK하이닉스 양산관리 면접 연습" \
  -o practice.html

node ../report/build/pdf.js practice.html "SK하이닉스_양산관리_면접연습.pdf" "SK하이닉스 양산관리 면접 연습"
echo "완료: interview/SK하이닉스_양산관리_면접연습.pdf"
