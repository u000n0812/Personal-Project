# 몽블랑 (Mongblanc)

Gemini 무료 API로 꿈을 해몽하고, 오늘의 타로 한 장을 뽑아보는 밤의 앱.

- **꿈 해몽**: 꿈 내용을 적으면 Gemini가 상징·분위기·조언으로 풀어줘요.
- **오늘의 타로**: 하루 한 번, 카드를 뽑아 오늘의 한마디를 받아요.
- **히스토리**: 지난 기록을 Vercel Postgres에 저장해서 날짜별로 모아봐요.
- 로그인 없이 브라우저 쿠키의 익명 ID로 "내 기록"만 구분해요.

## 로컬 개발 준비

1. 의존성 설치
   ```bash
   npm install
   ```

2. 환경 변수 설정 — `.env.example`을 복사해서 `.env.local`을 만들고 값을 채워주세요.
   ```bash
   cp .env.example .env.local
   ```
   - `GEMINI_API_KEY`: [Google AI Studio](https://aistudio.google.com/apikey)에서 무료로 발급.
   - `DATABASE_URL`, `DIRECT_URL`: Vercel 프로젝트의 **Storage → Postgres**에서 Neon Postgres를 추가하면 자동으로 발급돼요. 로컬 개발용으로는 로컬 Postgres나 Neon의 무료 브랜치를 하나 더 만들어 써도 돼요.

3. DB 스키마 반영 (최초 1회 및 스키마 변경 시)
   ```bash
   npm run db:push
   ```

4. 개발 서버 실행
   ```bash
   npm run dev
   ```
   http://localhost:3000 에서 확인.

## Vercel 배포

1. GitHub 저장소를 Vercel 프로젝트로 import.
2. 프로젝트의 **Storage** 탭에서 Postgres(Neon)를 추가하면 `DATABASE_URL`/`DIRECT_URL`이 자동으로 환경 변수에 연결돼요.
3. **Settings → Environment Variables**에 `GEMINI_API_KEY`를 추가.
4. 배포 후 최초 1회 `npm run db:push`를 로컬에서 프로덕션 `DATABASE_URL`로 실행하거나, Vercel의 배포 파이프라인에 같은 명령을 빌드 스텝으로 추가해 스키마를 반영하세요.

## 무료 티어 관련 제한

- Gemini API 무료 등급은 분당·일일 요청 수 제한이 있어요. `src/app/api/interpret/route.ts`에서 사용자당 하루 5회로 제한하고 있어요.
- 오늘의 타로는 `src/app/api/tarot/route.ts`에서 사용자당 하루 1회로 제한(같은 날 재요청 시 이미 뽑은 카드를 그대로 반환)돼요.
- Vercel Postgres 무료 티어는 저장 용량과 컴퓨팅 시간에 한도가 있어요. 사용량이 늘면 Neon 대시보드에서 확인하세요.

## 기술 스택

- Next.js (App Router) + TypeScript + Tailwind CSS
- Prisma + Vercel Postgres (Neon)
- `@google/generative-ai` (`gemini-2.0-flash`)
- 익명 사용자 식별: `src/middleware.ts`에서 발급하는 `mb_uid` 쿠키
