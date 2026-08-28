import type { Metadata } from "next";
import { Noto_Serif_KR, Noto_Sans_KR, JetBrains_Mono } from "next/font/google";
import NavBar from "@/components/NavBar";
import "./globals.css";

const notoSerifKr = Noto_Serif_KR({
  variable: "--font-noto-serif-kr",
  subsets: ["latin"],
  weight: ["500", "600", "700"],
});

const notoSansKr = Noto_Sans_KR({
  variable: "--font-noto-sans-kr",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

const jetbrainsMono = JetBrains_Mono({
  variable: "--font-jetbrains-mono",
  subsets: ["latin"],
  weight: ["400", "500"],
});

export const metadata: Metadata = {
  title: "몽블랑 — 오늘 밤의 꿈과 운을 풀어드려요",
  description: "Gemini로 꿈을 해몽하고, 오늘의 타로 한 장을 뽑아보는 밤의 앱, 몽블랑.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="ko"
      className={`${notoSerifKr.variable} ${notoSansKr.variable} ${jetbrainsMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        <NavBar />
        <main className="mx-auto w-full max-w-2xl flex-1 px-5 py-10">{children}</main>
        <footer className="mx-auto w-full max-w-2xl px-5 pb-10 text-xs text-ink-faint">
          몽블랑은 참고용 콘텐츠이며, 중요한 결정은 스스로의 판단을 따라주세요.
        </footer>
      </body>
    </html>
  );
}
