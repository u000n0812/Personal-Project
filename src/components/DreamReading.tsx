export type DreamSymbol = { name: string; meaning: string };

export type DreamFortune = {
  wealth: string;
  relationship: string;
  love: string;
  health: string;
  omen: string;
};

export type DreamResult = {
  title: string;
  mood: string;
  traditional: string;
  psychological: string;
  symbols: DreamSymbol[];
  fortune: DreamFortune;
  advice: string;
};

const FORTUNE_FIELDS: { key: keyof DreamFortune; label: string; icon: string }[] = [
  { key: "wealth", label: "재물", icon: "💰" },
  { key: "relationship", label: "인간관계", icon: "🤝" },
  { key: "love", label: "연애·결혼", icon: "💞" },
  { key: "health", label: "건강", icon: "🌿" },
  { key: "omen", label: "사건 징조", icon: "🔮" },
];

/**
 * 해몽 결과 본문. 해몽 직후 화면과 히스토리 상세 화면이 같은 컴포넌트를 쓴다.
 * 예전에 저장된 기록에는 전통·심리·영역별 풀이가 없을 수 있어 각 칸을 개별로 검사한다.
 */
export default function DreamReading({ result }: { result: DreamResult }) {
  const fortuneEntries = FORTUNE_FIELDS.filter((field) => result.fortune?.[field.key]);

  return (
    <>
      {result.mood && (
        <span className="mb-3 inline-flex items-center gap-1.5 rounded-full bg-gold/15 px-3 py-1 text-xs text-gold">
          <span className="h-1.5 w-1.5 rounded-full bg-gold" />
          {result.mood}
        </span>
      )}
      <h2 className="mb-5 font-serif text-lg font-bold text-ink">{result.title}</h2>

      {(result.traditional || result.psychological) && (
        <div className="flex flex-col gap-3">
          {result.traditional && (
            <section className="rounded-xl border border-gold/25 bg-gold/[0.07] p-4">
              <h3 className="mb-1.5 flex items-center gap-1.5 text-sm font-bold text-gold">
                <span>📜</span> 전통 해몽
              </h3>
              <p className="text-sm leading-relaxed text-ink-dim">{result.traditional}</p>
            </section>
          )}
          {result.psychological && (
            <section className="rounded-xl border border-accent/25 bg-accent/[0.07] p-4">
              <h3 className="mb-1.5 flex items-center gap-1.5 text-sm font-bold text-accent">
                <span>🧠</span> 심리학 관점
              </h3>
              <p className="text-sm leading-relaxed text-ink-dim">
                {result.psychological}
              </p>
            </section>
          )}
        </div>
      )}

      {result.symbols?.length > 0 && (
        <>
          <h3 className="mt-6 mb-2 text-sm font-bold text-ink">꿈속 상징</h3>
          <div className="flex flex-col divide-y divide-white/10">
            {result.symbols.map((symbol) => (
              <div key={symbol.name} className="flex justify-between gap-4 py-2.5 text-sm">
                <span className="shrink-0 font-semibold text-ink">{symbol.name}</span>
                <span className="text-right text-ink-dim">{symbol.meaning}</span>
              </div>
            ))}
          </div>
        </>
      )}

      {fortuneEntries.length > 0 && (
        <>
          <h3 className="mt-6 mb-2 text-sm font-bold text-ink">이 꿈이 말해주는 것</h3>
          <div className="flex flex-col gap-2">
            {fortuneEntries.map((field) => (
              <div key={field.key} className="rounded-xl bg-white/5 p-3.5">
                <p className="mb-1 flex items-center gap-1.5 text-xs font-semibold text-ink">
                  <span>{field.icon}</span> {field.label}
                </p>
                <p className="text-sm leading-relaxed text-ink-dim">
                  {result.fortune[field.key]}
                </p>
              </div>
            ))}
          </div>
        </>
      )}

      {result.advice && (
        <div className="mt-4 rounded-xl border border-white/10 bg-white/[0.07] p-3.5 text-sm leading-relaxed text-ink-dim">
          <b className="text-ink">오늘의 조언</b>
          <br />
          {result.advice}
        </div>
      )}
    </>
  );
}
