import { prisma } from "@/lib/prisma";
import { getUserId } from "@/lib/userId";
import { formatKoreanDate } from "@/lib/date";

export const dynamic = "force-dynamic";

type Entry = {
  id: string;
  type: "DREAM" | "TAROT";
  title: string | null;
  mood: string | null;
  cardName: string | null;
  cardKeyword: string | null;
  reversed: boolean | null;
  tarotAdvice: string | null;
  createdAt: Date;
};

function EntryList({
  entries,
  icon,
  accent,
  emptyText,
}: {
  entries: Entry[];
  icon: string;
  accent: string;
  emptyText: string;
}) {
  if (entries.length === 0) {
    return (
      <p className="rounded-2xl border border-dashed border-line px-4 py-8 text-center text-sm text-ink-faint">
        {emptyText}
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-2.5">
      {entries.map((entry) => {
        const isDream = entry.type === "DREAM";
        return (
          <div
            key={entry.id}
            className="flex items-start gap-3 rounded-2xl border border-line bg-surface p-4"
          >
            <div
              className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-sm ${accent}`}
            >
              {icon}
            </div>
            <div className="min-w-0 flex-1">
              <p className="font-mono text-[10.5px] text-ink-faint">
                {formatKoreanDate(entry.createdAt)}
              </p>
              <p className="truncate text-sm font-semibold text-ink">
                {isDream
                  ? entry.title
                  : `${entry.cardName}${entry.reversed ? " (역방향)" : ""}`}
              </p>
              <p className="truncate text-xs text-ink-dim">
                {isDream ? entry.mood : entry.tarotAdvice}
              </p>
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default async function HistoryPage() {
  const userId = await getUserId();
  const entries = userId
    ? await prisma.entry.findMany({
        where: { userId },
        orderBy: { createdAt: "desc" },
        take: 100,
      })
    : [];

  const dreams = entries.filter((entry) => entry.type === "DREAM");
  const tarots = entries.filter((entry) => entry.type === "TAROT");

  return (
    <div className="flex flex-col gap-8">
      <header>
        <p className="mb-2 font-mono text-xs tracking-[0.04em] text-accent">히스토리</p>
        <h1 className="font-serif text-2xl font-bold text-ink text-balance">
          지난 기록 {entries.length}건
        </h1>
      </header>

      <section className="flex flex-col gap-3">
        <h2 className="flex items-baseline gap-2 border-b border-line pb-2">
          <span className="font-serif text-base font-bold text-ink">🌙 꿈 해몽</span>
          <span className="font-mono text-xs text-ink-faint">{dreams.length}건</span>
        </h2>
        <EntryList
          entries={dreams}
          icon="🌙"
          accent="bg-accent/20"
          emptyText="아직 해몽 기록이 없어요."
        />
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="flex items-baseline gap-2 border-b border-line pb-2">
          <span className="font-serif text-base font-bold text-ink">🃏 오늘의 타로</span>
          <span className="font-mono text-xs text-ink-faint">{tarots.length}건</span>
        </h2>
        <EntryList
          entries={tarots}
          icon="🃏"
          accent="bg-gold/20"
          emptyText="아직 타로 기록이 없어요."
        />
      </section>
    </div>
  );
}
