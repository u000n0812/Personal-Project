import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { getUserId } from "@/lib/userId";
import { readTarot } from "@/lib/gemini";
import { TAROT_DECK } from "@/data/tarot";
import { todayRangeUTC } from "@/lib/date";

async function findTodaysDraw(userId: string) {
  const { start, end } = todayRangeUTC();
  return prisma.entry.findFirst({
    where: { userId, type: "TAROT", createdAt: { gte: start, lt: end } },
    orderBy: { createdAt: "desc" },
  });
}

export async function GET() {
  const userId = await getUserId();
  if (!userId) return NextResponse.json({ entry: null });
  try {
    const entry = await findTodaysDraw(userId);
    return NextResponse.json({ entry });
  } catch (error) {
    console.error("[api/tarot] GET failed", error);
    return NextResponse.json({ entry: null });
  }
}

export async function POST() {
  const userId = await getUserId();
  if (!userId) {
    return NextResponse.json(
      { error: "사용자 식별에 실패했어요. 새로고침 후 다시 시도해주세요." },
      { status: 400 }
    );
  }

  try {
    const existing = await findTodaysDraw(userId);
    if (existing) {
      return NextResponse.json({ entry: existing, alreadyDrawn: true });
    }

    const card = TAROT_DECK[Math.floor(Math.random() * TAROT_DECK.length)];
    const reversed = Math.random() < 0.35;
    const { label } = todayRangeUTC();
    const advice = await readTarot(card, reversed, label);
    const entry = await prisma.entry.create({
      data: {
        userId,
        type: "TAROT",
        cardName: card.name,
        cardKeyword: card.keyword,
        reversed,
        tarotAdvice: advice,
      },
    });
    return NextResponse.json({ entry, alreadyDrawn: false });
  } catch (error) {
    console.error("[api/tarot] failed", error);
    return NextResponse.json(
      { error: "카드를 읽는 중 문제가 생겼어요. 잠시 후 다시 시도해주세요." },
      { status: 502 }
    );
  }
}
