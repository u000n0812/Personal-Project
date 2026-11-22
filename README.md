# 몽블랑 (Mongblanc)

Gemini로 꿈을 해몽하고, 오늘의 타로 한 장을 뽑아보는 밤의 앱.

- **꿈 해몽** — 꿈 내용을 적으면 상징·분위기·조언으로 풀어줘요.
- **오늘의 타로** — 하루 한 번, 카드를 뽑아 오늘의 한마디를 받아요.
- **히스토리** — 지난 기록을 데이터베이스에 저장해 날짜별로 모아봐요.
- 회원가입 없이 브라우저에 발급되는 익명 ID로 "내 기록"만 구분해요.

## 배포하기 (약 3분)

아래 버튼을 누르면 저장소가 복제되고, Postgres 데이터베이스가 자동으로 만들어지며,
API 키를 입력하는 화면이 나와요. DB 테이블은 첫 배포 때 자동 생성되니 따로 할 일은 없어요.

[![Vercel로 배포하기](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https%3A%2F%2Fgithub.com%2Fu000n0812%2FPersonal-Project&project-name=monblanc&repository-name=monblanc&env=GEMINI_API_KEY&envDescription=Google%20AI%20Studio%EC%97%90%EC%84%9C%20%EB%AC%B4%EB%A3%8C%EB%A1%9C%20%EB%B0%9C%EA%B8%89%ED%95%98%EB%8A%94%20Gemini%20API%20%ED%82%A4&envLink=https%3A%2F%2Faistudio.google.com%2Fapikey&stores=%5B%7B%22type%22%3A%22postgres%22%7D%5D)

배포가 끝나면 `https://<프로젝트이름>.vercel.app` 주소가 나오고, **그 주소를 아는 사람은 누구나 바로 사용할 수 있어요.** 각자 자기 브라우저의 익명 ID로 구분되니 기록이 서로 섞이지 않아요.

> 버튼이 필요로 하는 값은 `GEMINI_API_KEY` 하나뿐이에요.
> [Google AI Studio](https://aistudio.google.com/apikey)에서 무료로 발급받을 수 있어요.
> `DATABASE_URL`은 Postgres를 붙이면 Vercel이 자동으로 채워줘요.

## 로컬에서 실행하기

1. 의존성 설치
   ```bash
   npm install
   ```

2. 환경 변수 설정 — `.env.example`을 복사해서 `.env`를 만들고 값을 채워주세요.
   ```bash
   cp .env.example .env
   ```
   - `GEMINI_API_KEY`: [Google AI Studio](https://aistudio.google.com/apikey)에서 발급.
   - `DATABASE_URL`: 로컬 Postgres 또는 Neon 무료 브랜치 주소.

3. DB 테이블 생성
   ```bash
   npm run db:migrate
   ```

4. 개발 서버 실행
   ```bash
   npm run dev
   ```
   http://localhost:3000 에서 확인.

## 사용량 제한

무료 등급 한도를 넘지 않도록 앱 자체에 제한을 넣어뒀어요.

| 기능 | 제한 | 위치 |
| --- | --- | --- |
| 꿈 해몽 | 사용자당 하루 5회 | `src/app/api/interpret/route.ts` |
| 오늘의 타로 | 사용자당 하루 1회 (재요청 시 같은 카드 반환) | `src/app/api/tarot/route.ts` |

숫자를 바꾸고 싶으면 각 파일 위쪽의 `DAILY_LIMIT` 상수를 고치면 돼요.

## 카드 그림 출처

`public/tarot`의 78장은 라이더-웨이트-스미스 덱(1909, Pamela Colman Smith 그림)입니다.
저작권이 만료되어 퍼블릭 도메인으로 통용되는 판본이며, npm 패키지
[`@cometpisces/tarot-kit-images`](https://www.npmjs.com/package/@cometpisces/tarot-kit-images)에서
받아 WebP로 변환해 담았습니다. 다만 배포처의 안내대로 국가별 저작권 해석이 다를 수 있으니,
상업적으로 크게 쓸 계획이라면 해당 지역 기준을 한 번 확인해주세요.

## 기술 스택

- Next.js (App Router) + TypeScript + Tailwind CSS
- Prisma + Postgres (Vercel Storage / Neon)
- `@google/genai` (`gemini-3.6-flash`)
- 익명 사용자 식별: `src/proxy.ts`가 발급하는 `mb_uid` 쿠키

## 참고

몽블랑이 내놓는 해석은 재미와 참고를 위한 콘텐츠예요. 중요한 결정은 스스로의 판단을 따라주세요.
