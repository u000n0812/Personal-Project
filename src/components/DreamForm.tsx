"use client";

import { useState } from "react";
import DreamReading, { type DreamResult } from "@/components/DreamReading";

/**
 * 플루칙(Plutchik)의 8가지 기본 감정을 뼈대로, 꿈에서 특히 자주 나타나는
 * 불안·혼란·평온을 더한 11개. 이 조합이면 대부분의 꿈 감정이 이 안에 들어온다.
 */
const MOOD_OPTIONS = [
  "😊 기쁨",
  "💓 설렘",
  "🥰 애정",
  "🕊️ 평온",
  "😢 슬픔",
  "😠 분노",
  "😨 두려움",
  "😰 불안",
  "😲 놀람",
  "🤢 혐오",
  "😵‍💫 혼란",
];

const MAX_LENGTH = 1000;

export default function DreamForm() {
  const [dreamText, setDreamText] = useState("");
  const [moodTags, setMoodTags] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<DreamResult | null>(null);

  function toggleTag(tag: string) {
    setMoodTags((prev) =>
      prev.includes(tag) ? prev.filter((t) => t !== tag) : [...prev, tag]
    );
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!dreamText.trim() || loading) return;

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const res = await fetch("/api/interpret", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ dreamText, moodTags }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error ?? "해몽을 만드는 중 문제가 생겼어요.");
      }
      setResult(data.entry);
    } catch (err) {
      setError(err instanceof Error ? err.message : "알 수 없는 오류가 발생했어요.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <div className="rounded-2xl border border-line bg-surface p-5 shadow-[0_20px_50px_-25px_rgba(0,0,0,0.6)]">
          <label htmlFor="dream" className="mb-2 block text-xs text-ink-dim">
            꿈 내용
          </label>
          <textarea
            id="dream"
            value={dreamText}
            onChange={(e) => setDreamText(e.target.value.slice(0, MAX_LENGTH))}
            placeholder="어젯밤 어떤 꿈을 꾸셨나요? 기억나는 만큼 자유롭게 적어주세요..."
            rows={6}
            className="w-full resize-none rounded-xl border border-white/10 bg-white/5 p-3.5 text-sm text-ink placeholder:text-ink-faint focus:border-accent focus:outline-none"
          />
          <div className="mt-1 text-right font-mono text-[11px] text-ink-faint">
            {dreamText.length}/{MAX_LENGTH}
          </div>

          <div className="mt-3 flex flex-wrap gap-2">
            {MOOD_OPTIONS.map((tag) => {
              const active = moodTags.includes(tag);
              return (
                <button
                  key={tag}
                  type="button"
                  onClick={() => toggleTag(tag)}
                  className={`rounded-full px-3 py-1.5 text-xs transition-colors ${
                    active
                      ? "bg-accent-strong/30 text-ink"
                      : "bg-white/5 text-ink-dim hover:bg-white/10"
                  }`}
                >
                  {tag}
                </button>
              );
            })}
          </div>

          <button
            type="submit"
            disabled={!dreamText.trim() || loading}
            className="mt-5 w-full rounded-xl bg-gradient-to-r from-accent to-accent-strong py-3.5 text-sm font-bold text-[#150f30] transition-opacity disabled:opacity-40"
          >
            {loading ? "해몽하는 중..." : "해몽 보기"}
          </button>
        </div>
      </form>

      {error && (
        <p className="rounded-xl border border-gold/30 bg-gold/10 p-3.5 text-sm text-gold">
          {error}
        </p>
      )}

      {result && (
        <div className="animate-[fadeIn_0.3s_ease] rounded-2xl border border-line bg-surface p-5">
          <DreamReading result={result} />
        </div>
      )}
    </div>
  );
}
