import Image from "next/image";
import { findCardByName } from "@/data/tarot";

/**
 * 라이더-웨이트 카드 그림. 역방향이면 실제 타로처럼 180도 뒤집어 보여준다.
 * 덱에 없는 이름(예전 기록)이면 그림 없이 이름만 담은 카드로 대체한다.
 */
export default function TarotCardImage({
  cardName,
  cardKeyword,
  reversed,
}: {
  cardName: string | null;
  cardKeyword?: string | null;
  reversed?: boolean | null;
}) {
  const card = findCardByName(cardName);

  return (
    <figure className="mx-auto flex w-full max-w-[260px] flex-col items-center gap-3">
      <div className="relative w-full overflow-hidden rounded-2xl border border-gold/40 bg-[#150f2c] shadow-[0_20px_50px_-20px_rgba(0,0,0,0.7)]">
        {card ? (
          <Image
            src={card.image}
            alt={`${card.name}${reversed ? " 역방향" : ""} 카드 그림`}
            width={600}
            height={1054}
            sizes="260px"
            priority
            className={`h-auto w-full ${reversed ? "rotate-180" : ""}`}
          />
        ) : (
          <div className="flex aspect-[600/1054] items-center justify-center p-4 text-center">
            <span className="font-serif text-base font-bold text-ink">{cardName}</span>
          </div>
        )}
      </div>

      <figcaption className="flex flex-col items-center gap-1">
        <p className="font-serif text-lg font-bold text-ink">{cardName}</p>
        <p className="font-mono text-[11px] text-ink-dim">
          {cardKeyword}
          {cardKeyword ? " · " : ""}
          {reversed ? "역방향" : "정방향"}
        </p>
      </figcaption>
    </figure>
  );
}
