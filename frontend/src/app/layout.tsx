import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { Sidebar } from "@/components/layout/Sidebar";
import { Header } from "@/components/layout/Header";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });
const jetbrainsMono = JetBrains_Mono({ subsets: ["latin"], variable: "--font-mono" });

export const metadata: Metadata = {
  title: { default: "MW StockMarket Analytics", template: "%s — MW Analytics" },
  description:
    "AI-powered stock market video intelligence platform. Discover, analyze and chat with financial YouTube content.",
  keywords: ["stock market", "AI", "video intelligence", "financial analysis", "investment"],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning className={`${inter.variable} ${jetbrainsMono.variable}`}>
      <head />
      <body className="antialiased">
        <div className="flex h-screen overflow-hidden" style={{ background: "var(--bg-base)" }}>
          <Sidebar />
          <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
            <Header />
            <main className="flex-1 overflow-y-auto">
              {children}
            </main>
          </div>
        </div>
      </body>
    </html>
  );
}
