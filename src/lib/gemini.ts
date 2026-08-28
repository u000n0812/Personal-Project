import { GoogleGenerativeAI } from "@google/generative-ai";
import type { TarotCard } from "@/data/tarot";

const MODEL_NAME = "gemini-2.0-flash";

function getModel() {
  const apiKey = process.env.GEMINI_API_KEY;
  if (!apiKey) {
    throw new Error(
      "GEMINI_API_KEY가 설정되어 있지 않아요. .env.local에 Google AI Studio에서 발급한 키를 넣어주세요."
    );
  }
  const genAI = new GoogleGenerativeAI(apiKey);
  return genAI.getGenerativeModel({
    model: MODEL_NAME,
    generationConfig: { responseMimeType: "application/json" },
  });
}

export type DreamSymbol = { name: string; meaning: string };

export type DreamInterpretation = {
  title: string;
  mood: string;
  symbols: DreamSymbol[];
  advice: string;
};

function extractJson(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    const match = text.match(/\{[\s\S]*\}/);
    if (match) return JSON.parse(match[0]);
    throw new Error("Gemini 응답을 해석할 수 없어요.");
  }
}

export async function interpretDream(
  dreamText: string,
  moodTags: string[]
): Promise<DreamInterpretation> {
  const model = getModel();
  const prompt = `당신은 따뜻하고 통찰력 있는 해몽가입니다. 아래 꿈 이야기를 한국어로 해석해주세요.
전통 해몽과 심리학적 관점을 함께 참고하되, 불안을 조장하지 말고 공감과 위로가 느껴지도록 적어주세요.

꿈 내용: """${dreamText}"""
사용자가 고른 감정 태그: ${moodTags.length ? moodTags.join(", ") : "없음"}

아래 JSON 형식으로만 답하세요. 다른 설명이나 마크다운은 절대 포함하지 마세요.
{
  "title": "꿈을 요약하는 짧은 제목 (15자 내외)",
  "mood": "꿈 전체 분위기를 나타내는 한 문장 (예: 전체적으로 불안·긴장)",
  "symbols": [
    { "name": "꿈에 등장한 상징", "meaning": "그 상징에 대한 해석 한두 문장" }
  ],
  "advice": "오늘 하루에 도움이 될 조언 한두 문장"
}
symbols는 2개에서 4개 사이로 뽑아주세요.`;

  const result = await model.generateContent(prompt);
  const parsed = extractJson(result.response.text()) as DreamInterpretation;

  if (!parsed.title || !parsed.mood || !Array.isArray(parsed.symbols) || !parsed.advice) {
    throw new Error("Gemini 응답 형식이 올바르지 않아요.");
  }
  return parsed;
}

export async function readTarot(
  card: TarotCard,
  reversed: boolean,
  dateLabel: string
): Promise<string> {
  const model = getModel();
  const prompt = `당신은 다정한 타로 리더입니다. 아래 카드를 바탕으로 오늘(${dateLabel})의 운세를 한국어 2~3문장으로 짧게 적어주세요.
과장된 예언 투가 아니라, 담백하고 실용적인 조언 톤으로 적어주세요.

카드: ${card.name} (${card.keyword})
방향: ${reversed ? "역방향" : "정방향"}
카드의 기본 의미: ${reversed ? card.reversedMeaning : card.uprightMeaning}

아래 JSON 형식으로만 답하세요. 다른 설명이나 마크다운은 절대 포함하지 마세요.
{ "advice": "오늘의 한마디" }`;

  const result = await model.generateContent(prompt);
  const parsed = extractJson(result.response.text()) as { advice: string };

  if (!parsed.advice) {
    throw new Error("Gemini 응답 형식이 올바르지 않아요.");
  }
  return parsed.advice;
}
