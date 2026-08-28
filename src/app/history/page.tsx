import { prisma } from "@/lib/prisma";
import { getUserId } from "@/lib/userId";
import { formatKoreanDate } from "@/lib/date";

export const dynamic = "force-dynamic";

export default async function HistoryPage() {
  const userId = await getUserId();
  const entries = userId
    ? await prisma.entry.findMany({
        where: { userId },
        orderBy: { createdAt: "desc" },
        take: 50,
      })
    : [];

  return (
    <div className="flex flex-col gap-6">
      <header>
        <p className="mb-2 font-mono text-xs uppercase tracking-[0.14em] text-accent">
          히스토리
        </p>
        <h1 className="font-serif text-2xl font-bold text-ink text-balance">
          지난 기록 {entries.length}건
        </h1>
        <p className="mt-1.5 text-sm text-ink-dim">
          꿈 해몽과 타로 기록을 날짜순으로 모아봤어요.
        </p>
      </header>

      {entries.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-line p-8 text-center text-sm text-ink-faint">
          아직 기록이 없어요. 꿈을 해몽하거나 오늘의 타로를 뽑아보세요.
        </div>
      ) : (
        <div className="flex flex-col gap-2.5">
          {entries.map((entry) => {
            const isDream = entry.type === "DREAM";
            return (
              <div
                key={entry.id}
                className="flex items-start gap-3 rounded-2xl border border-line bg-surface p-4"
              >
                <div
                  className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-sm ${
                    isDream ? "bg-accent/20" : "bg-gold/20"
                  }`}
                >
                  {isDream ? "🌙" : "🃏"}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="font-mono text-[10.5px] text-ink-faint">
                    {formatKoreanDate(entry.createdAt)}
                  </p>
                  <p className="truncate text-sm font-semibold text-ink">
                    {isDream ? entry.title : entry.cardName}
                  </p>
                  <p className="truncate text-xs text-ink-dim">
                    {isDream ? entry.mood : entry.tarotAdvice}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      )}

      <p className="flex items-center gap-1.5 self-start font-mono text-[10.5px] text-ink-faint">
        <span className="text-gold">⛁</span> Vercel Postgres에서 불러옴
      </p>
    </div>
  );
}
