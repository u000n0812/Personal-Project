import DreamForm from "@/components/DreamForm";

export default function Home() {
  return (
    <div className="flex flex-col gap-6">
      <header>
        <p className="mb-2 font-mono text-xs tracking-[0.04em] text-accent">
          꿈 해몽
        </p>
        <h1 className="font-serif text-2xl font-bold text-ink text-balance">
          오늘 꾼 꿈을 들려주세요
        </h1>
        <p className="mt-1.5 text-sm text-ink-dim">
          기억나는 만큼만 적어도 괜찮아요. 상징과 감정을 함께 풀어드릴게요.
        </p>
      </header>
      <DreamForm />
    </div>
  );
}
