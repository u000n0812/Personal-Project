"use client";

import { useEffect, useState } from "react";

type TarotResult = {
  cardName: string;
  cardKeyword: string;
  reversed: boolean;
  tarotAdvice: string;
  createdAt: string;
};

export default function TarotDraw() {
  const [loading, setLoading] = useState(true);
  const [drawing, setDrawing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<TarotResult | null>(null);

  useEffect(() => {
    fetch("/api/tarot")
      .then((res) => res.json())
      .then((data) => setResult(data.entry ?? null))
      .catch(() => setError("오늘의 카드를 불러오지 못했어요."))
      .finally(() => setLoading(false));
  }, []);

  async function draw() {
    if (drawing) return;
    setDrawing(true);
    setError(null);
    try {
      const res = await fetch("/api/tarot", { method: "POST" });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error ?? "카드를 읽는 중 문제가 생겼어요.");
      setResult(data.entry);
    } catch (err) {
      setError(err instanceof Error ? err.message : "알 수 없는 오류가 발생했어요.");
    } finally {
      setDrawing(false);
    }
  }

  if (loading) {
    return (
      <div className="flex aspect-[5/7] max-w-xs animate-pulse items-center justify-center rounded-2xl border border-line bg-surface text-sm text-ink-faint">
        불러오는 중...
      </div>
    );
  }

  if (!result) {
    return (
      <div className="flex flex-col items-center gap-5">
        <button
          onClick={draw}
          disabled={drawing}
          className="group relative flex aspect-[5/7] w-full max-w-xs flex-col items-center justify-center gap-3 rounded-2xl border border-gold/40 bg-[radial-gradient(circle_at_50%_30%,rgba(224,183,104,0.18),transparent_55%),linear-gradient(155deg,#2c2258,#150f2c_70%)] transition-transform hover:scale-[1.02] disabled:opacity-60"
        >
          <span className="text-3xl">✦</span>
          <span className="font-serif text-lg font-bold text-ink">
            {drawing ? "카드를 읽는 중..." : "오늘의 카드 뽑기"}
          </span>
          <span className="font-mono text-[11px] text-ink-dim">
            하루에 한 번 뽑을 수 있어요
          </span>
        </button>
        {error && (
          <p className="rounded-xl border border-gold/30 bg-gold/10 p-3.5 text-sm text-gold">
            {error}
          </p>
        )}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="mx-auto flex aspect-[5/7] w-full max-w-xs flex-col items-center justify-center gap-2 rounded-2xl border border-gold/40 bg-[radial-gradient(circle_at_50%_30%,rgba(224,183,104,0.28),transparent_55%),linear-gradient(155deg,#2c2258,#150f2c_70%)]">
        <span className="text-3xl text-gold">✦</span>
        <p className="font-serif text-lg font-bold text-ink">{result.cardName}</p>
        <p className="font-mono text-[11px] text-ink-dim">
          {result.cardKeyword} · {result.reversed ? "역방향" : "정방향"}
        </p>
      </div>

      <div className="rounded-2xl border border-line bg-surface p-5">
        <b className="mb-1.5 block text-sm text-ink">오늘의 한마디</b>
        <p className="text-sm leading-relaxed text-ink-dim">{result.tarotAdvice}</p>
      </div>
    </div>
  );
}
