/** UTC-day boundaries, used so "today" is stable for a given calendar day regardless of request timing. */
export function todayRangeUTC(): { start: Date; end: Date; label: string } {
  const now = new Date();
  const start = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate()));
  const end = new Date(start.getTime() + 24 * 60 * 60 * 1000);
  return { start, end, label: start.toISOString().slice(0, 10) };
}

export function formatKoreanDate(date: Date): string {
  return new Intl.DateTimeFormat("ko-KR", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(date);
}
