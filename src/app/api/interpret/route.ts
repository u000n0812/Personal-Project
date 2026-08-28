import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { getUserId } from "@/lib/userId";
import { interpretDream } from "@/lib/gemini";

const MAX_LENGTH = 1000;
const DAILY_LIMIT = 5;

export async function POST(request: NextRequest) {
  const userId = await getUserId();
  if (!userId) {
    return NextResponse.json(
      { error: "사용자 식별에 실패했어요. 새로고침 후 다시 시도해주세요." },
      { status: 400 }
    );
  }

  const body = await request.json().catch(() => null);
  const dreamText = typeof body?.dreamText === "string" ? body.dreamText.trim() : "";
  const moodTags = Array.isArray(body?.moodTags)
    ? body.moodTags.filter((tag: unknown) => typeof tag === "string").slice(0, 5)
    : [];

  if (!dreamText) {
    return NextResponse.json({ error: "꿈 내용을 입력해주세요." }, { status: 400 });
  }
  if (dreamText.length > MAX_LENGTH) {
    return NextResponse.json(
      { error: `꿈 내용은 ${MAX_LENGTH}자 이내로 적어주세요.` },
      { status: 400 }
    );
  }

  try {
    const since = new Date(Date.now() - 24 * 60 * 60 * 1000);
    const countToday = await prisma.entry.count({
      where: { userId, type: "DREAM", createdAt: { gte: since } },
    });
    if (countToday >= DAILY_LIMIT) {
      return NextResponse.json(
        { error: `무료 API 한도를 지키기 위해 하루 ${DAILY_LIMIT}번까지만 해몽할 수 있어요. 내일 다시 찾아주세요.` },
        { status: 429 }
      );
    }

    const interpretation = await interpretDream(dreamText, moodTags);
    const entry = await prisma.entry.create({
      data: {
        userId,
        type: "DREAM",
        dreamText,
        title: interpretation.title,
        mood: interpretation.mood,
        symbols: interpretation.symbols,
        advice: interpretation.advice,
      },
    });
    return NextResponse.json({ entry });
  } catch (error) {
    console.error("[api/interpret] failed", error);
    return NextResponse.json(
      { error: "해몽을 만드는 중 문제가 생겼어요. 잠시 후 다시 시도해주세요." },
      { status: 502 }
    );
  }
}
