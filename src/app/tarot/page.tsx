import TarotDraw from "@/components/TarotDraw";

export default function TarotPage() {
  return (
    <div className="flex flex-col gap-6">
      <header>
        <p className="mb-2 font-mono text-xs uppercase tracking-[0.14em] text-gold">
          오늘의 타로
        </p>
        <h1 className="font-serif text-2xl font-bold text-ink text-balance">
          카드 한 장에 오늘 하루를 물어보세요
        </h1>
        <p className="mt-1.5 text-sm text-ink-dim">
          하루 한 번, 카드가 건네는 짧은 조언이에요.
        </p>
      </header>
      <TarotDraw />
    </div>
  );
}
