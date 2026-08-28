import { GoogleGenAI } from "@google/genai";
import type { TarotCard } from "@/data/tarot";

const MODEL_NAME = "gemini-3.6-flash";

function getClient() {
  const apiKey = process.env.GEMINI_API_KEY;
  if (!apiKey) {
    throw new Error(
      "GEMINI_API_KEY가 설정되어 있지 않아요. .env에 Google AI Studio에서 발급한 키를 넣어주세요."
    );
  }
  return new GoogleGenAI({ apiKey });
}

/** 같은 카드를 뽑아도 매번 다른 문장이 나오도록 온도를 높게 잡는다. */
async function generateJson(prompt: string, temperature = 1.1): Promise<unknown> {
  const ai = getClient();
  const response = await ai.models.generateContent({
    model: MODEL_NAME,
    contents: prompt,
    config: { responseMimeType: "application/json", temperature },
  });

  const text = response.text;
  if (!text) throw new Error("Gemini가 빈 응답을 반환했어요.");

  try {
    return JSON.parse(text);
  } catch {
    const match = text.match(/\{[\s\S]*\}/);
    if (match) return JSON.parse(match[0]);
    throw new Error("Gemini 응답을 해석할 수 없어요.");
  }
}

export type DreamSymbol = { name: string; meaning: string };

export type DreamFortune = {
  wealth: string;
  relationship: string;
  love: string;
  health: string;
  omen: string;
};

export type DreamInterpretation = {
  title: string;
  mood: string;
  traditional: string;
  psychological: string;
  symbols: DreamSymbol[];
  fortune: DreamFortune;
  advice: string;
};

const FORTUNE_KEYS: (keyof DreamFortune)[] = [
  "wealth",
  "relationship",
  "love",
  "health",
  "omen",
];

export async function interpretDream(
  dreamText: string,
  moodTags: string[]
): Promise<DreamInterpretation> {
  const prompt = `당신은 한국의 전통 해몽과 현대 심리학을 함께 다루는 해몽가입니다.
아래 꿈을 두 관점에서 해석하고, 그 해석을 바탕으로 생활 영역별 풀이를 적어주세요.

꿈 내용: """${dreamText}"""
사용자가 고른 감정: ${moodTags.length ? moodTags.join(", ") : "없음"}

작성 지침
- 전통 해몽: 한국 민간 해몽에서 이 소재를 어떻게 보아왔는지 근거를 들어 설명하세요. (예: 돼지·물·조상·불 등의 전통적 상징 의미)
- 심리학 관점: 융의 무의식·상징 이론이나 일상의 스트레스·욕구 같은 심리적 해석을 설명하세요.
- 영역별 풀이: 위 두 해석에서 자연스럽게 이어지도록 쓰고, 꿈과 무관한 내용을 지어내지 마세요.
  근거가 약한 영역은 단정하지 말고 "이 꿈에서는 크게 드러나지 않아요" 같이 솔직하게 적으세요.
- 불안을 조장하거나 겁주는 표현은 쓰지 말고, 담백하고 따뜻하게 적으세요.
- 각 항목은 2~3문장으로 적으세요.

아래 JSON 형식으로만 답하세요. 다른 설명이나 마크다운은 절대 포함하지 마세요.
{
  "title": "꿈을 요약하는 짧은 제목 (15자 내외)",
  "mood": "꿈 전체 분위기를 나타내는 한 문장",
  "traditional": "전통 해몽 관점의 해석",
  "psychological": "심리학 관점의 해석",
  "symbols": [
    { "name": "꿈에 등장한 상징", "meaning": "그 상징에 대한 해석 한두 문장" }
  ],
  "fortune": {
    "wealth": "재물운 풀이",
    "relationship": "인간관계 풀이",
    "love": "연애·결혼 풀이",
    "health": "건강 풀이",
    "omen": "앞으로의 사건 징조"
  },
  "advice": "오늘 하루에 도움이 될 조언 한두 문장"
}
symbols는 2개에서 4개 사이로 뽑아주세요.`;

  const parsed = (await generateJson(prompt, 0.9)) as DreamInterpretation;

  const missing =
    !parsed.title ||
    !parsed.mood ||
    !parsed.traditional ||
    !parsed.psychological ||
    !Array.isArray(parsed.symbols) ||
    !parsed.advice ||
    !parsed.fortune ||
    FORTUNE_KEYS.some((key) => !parsed.fortune[key]);

  if (missing) throw new Error("Gemini 응답 형식이 올바르지 않아요.");
  return parsed;
}

/** 같은 카드가 다시 나와도 표현이 반복되지 않도록 매번 다른 화법을 고른다. */
const TAROT_VOICES = [
  "차분하고 담백한 말투로",
  "다정하게 다독이는 말투로",
  "짧고 단단하게 핵심만 짚는 말투로",
  "이야기를 들려주듯 부드럽게",
  "현실적인 조언에 무게를 두고",
  "따뜻하지만 솔직하게",
];

const TAROT_ANGLES = [
  "오늘 하루의 마음가짐",
  "오늘 마주칠 사람과의 관계",
  "오늘 내려야 할 선택",
  "오늘 챙겨야 할 몸과 리듬",
  "오늘의 일과 성취",
  "오늘 놓치기 쉬운 것",
];

function pick<T>(list: T[]): T {
  return list[Math.floor(Math.random() * list.length)];
}

export async function readTarot(
  card: TarotCard,
  reversed: boolean,
  dateLabel: string
): Promise<string> {
  const prompt = `당신은 다정하면서도 현실적인 타로 리더입니다.
아래 카드로 오늘(${dateLabel})의 운세를 한국어 2~3문장으로 적어주세요.

카드: ${card.name} (${card.keyword})
방향: ${reversed ? "역방향" : "정방향"}
카드의 기본 의미: ${reversed ? card.reversedMeaning : card.uprightMeaning}

작성 지침
- ${pick(TAROT_VOICES)} 적어주세요.
- 이번에는 특히 "${pick(TAROT_ANGLES)}"에 초점을 맞춰주세요.
- 카드 이름을 그대로 반복하지 말고, 카드가 가리키는 상황을 풀어서 표현하세요.
- 과장된 예언이나 단정적인 불행 예고는 쓰지 마세요.
- "오늘은"으로 문장을 시작하지 마세요.

아래 JSON 형식으로만 답하세요. 다른 설명이나 마크다운은 절대 포함하지 마세요.
{ "advice": "오늘의 한마디" }`;

  const parsed = (await generateJson(prompt, 1.2)) as { advice: string };

  if (!parsed.advice) {
    throw new Error("Gemini 응답 형식이 올바르지 않아요.");
  }
  return parsed.advice;
}
