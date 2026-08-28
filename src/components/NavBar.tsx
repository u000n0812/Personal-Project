"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/", label: "꿈 해몽", icon: "🌙" },
  { href: "/tarot", label: "오늘의 타로", icon: "🃏" },
  { href: "/history", label: "히스토리", icon: "⛁" },
] as const;

export default function NavBar() {
  const pathname = usePathname();

  return (
    <nav className="sticky top-0 z-10 border-b border-line/70 bg-bg/80 backdrop-blur">
      <div className="mx-auto flex max-w-2xl items-center justify-between px-5 py-4">
        <Link href="/" className="flex items-baseline gap-1.5">
          <span className="font-serif text-lg font-bold tracking-tight text-ink">몽블랑</span>
          <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-ink-faint">
            Mongblanc
          </span>
        </Link>
        <div className="flex items-center gap-1">
          {LINKS.map((link) => {
            const active = pathname === link.href;
            return (
              <Link
                key={link.href}
                href={link.href}
                className={`rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${
                  active
                    ? "bg-accent-strong/25 text-ink"
                    : "text-ink-dim hover:text-ink"
                }`}
              >
                <span className="mr-1">{link.icon}</span>
                {link.label}
              </Link>
            );
          })}
        </div>
      </div>
    </nav>
  );
}
