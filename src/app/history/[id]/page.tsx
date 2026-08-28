import Link from "next/link";
import { notFound } from "next/navigation";
import { prisma } from "@/lib/prisma";
import { getUserId } from "@/lib/userId";
import { formatKoreanDate } from "@/lib/date";
import DreamReading, {
  type DreamFortune,
  type DreamSymbol,
} from "@/components/DreamReading";
import TarotCardImage from "@/components/TarotCardImage";

export const dynamic = "force-dynamic";

export default async function HistoryDetailPage({
  params,
}: PageProps<"/history/[id]">) {
  const { id } = await params;
  const userId = await getUserId();
  if (!userId) notFound();

  // userId를 함께 걸어 남의 기록을 id만으로 열어볼 수 없게 한다.
  const entry = await prisma.entry.findFirst({ where: { id, userId } });
  if (!entry) notFound();

  const isDream = entry.type === "DREAM";

  return (
    <div className="flex flex-col gap-5">
      <Link
        href="/history"
        className="flex w-fit items-center gap-1.5 text-xs text-ink-dim transition-colors hover:text-ink"
      >
        ← 히스토리로
      </Link>

      <p className="font-mono text-xs text-ink-faint">
        {formatKoreanDate(entry.createdAt)}
      </p>

      {isDream ? (
        <>
          <div className="rounded-2xl border border-line bg-surface p-5">
            <DreamReading
              result={{
                title: entry.title ?? "제목 없음",
                mood: entry.mood ?? "",
                traditional: entry.traditional ?? "",
                psychological: entry.psychological ?? "",
                symbols: (entry.symbols as DreamSymbol[] | null) ?? [],
                fortune: (entry.fortune as DreamFortune | null) ?? ({} as DreamFortune),
                advice: entry.advice ?? "",
              }}
            />
          </div>

          {entry.dreamText && (
            <section className="rounded-2xl border border-line bg-surface p-5">
              <h3 className="mb-2 text-sm font-bold text-ink">그날 적은 꿈</h3>
              <p className="text-sm leading-relaxed whitespace-pre-wrap text-ink-dim">
                {entry.dreamText}
              </p>
            </section>
          )}
        </>
      ) : (
        <>
          <TarotCardImage
            cardName={entry.cardName}
            cardKeyword={entry.cardKeyword}
            reversed={entry.reversed}
          />

          <div className="rounded-2xl border border-line bg-surface p-5">
            <b className="mb-1.5 block text-sm text-ink">그날의 한마디</b>
            <p className="text-sm leading-relaxed text-ink-dim">{entry.tarotAdvice}</p>
          </div>
        </>
      )}
    </div>
  );
}
