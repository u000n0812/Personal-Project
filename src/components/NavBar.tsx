"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/", label: "꿈 해몽", icon: "🌙" },
  { href: "/tarot", label: "오늘의 타로", icon: "🃏" },
  { href: "/history", label: "히스토리", icon: "⛁" },
] as const;

export function BrandBar() {
  return (
    <header className="sticky top-0 z-10 border-b border-line/70 bg-bg/80 backdrop-blur">
      <div className="mx-auto flex max-w-2xl items-baseline px-5 py-4">
        <Link href="/" className="font-serif text-lg font-bold tracking-tight text-ink">
          몽블랑
        </Link>
      </div>
    </header>
  );
}

export function TabBar() {
  const pathname = usePathname();

  return (
    <nav className="fixed inset-x-0 bottom-0 z-10 border-t border-line/70 bg-bg/90 backdrop-blur">
      <div className="mx-auto flex max-w-2xl">
        {LINKS.map((link) => {
          const active = pathname === link.href;
          return (
            <Link
              key={link.href}
              href={link.href}
              aria-current={active ? "page" : undefined}
              className={`flex flex-1 flex-col items-center gap-1 py-2.5 text-[11px] font-medium whitespace-nowrap transition-colors ${
                active ? "text-ink" : "text-ink-faint hover:text-ink-dim"
              }`}
            >
              <span
                className={`flex h-7 w-12 items-center justify-center rounded-full text-sm transition-colors ${
                  active ? "bg-accent-strong/30" : ""
                }`}
              >
                {link.icon}
              </span>
              {link.label}
            </Link>
          );
        })}
      </div>
      <div className="h-[env(safe-area-inset-bottom)]" />
    </nav>
  );
}
