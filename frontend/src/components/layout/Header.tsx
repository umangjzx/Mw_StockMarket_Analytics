"use client";

import { useState, useRef, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Search, X, Loader2, Command, Calendar } from "lucide-react";
import { companyApi } from "@/lib/api";
import { cn } from "@/lib/utils";

interface Candidate {
  symbol: string;
  company_name?: string;
  exchange?: string;
  sector?: string;
}

function useClock() {
  const [time, setTime] = useState(() => new Date());
  useEffect(() => {
    const id = setInterval(() => setTime(new Date()), 60_000);
    return () => clearInterval(id);
  }, []);
  return time;
}

export function Header() {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Candidate[]>([]);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const [focused, setFocused] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout>>(null);
  const now = useClock();

  // ⌘K / Ctrl+K shortcut
  useEffect(() => {
    function handler(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        inputRef.current?.focus();
      }
      if (e.key === "Escape") { setOpen(false); inputRef.current?.blur(); }
    }
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (!ref.current?.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  function handleInput(val: string) {
    setQuery(val);
    if (timerRef.current) clearTimeout(timerRef.current);
    if (!val.trim()) { setResults([]); setOpen(false); return; }
    timerRef.current = setTimeout(async () => {
      setLoading(true);
      try {
        const data: any = await companyApi.resolve(val);
        setResults(data?.candidates ?? []);
        setOpen(true);
      } catch {
        setResults([]);
      } finally {
        setLoading(false);
      }
    }, 280);
  }

  function pick(symbol: string) {
    setOpen(false); setQuery(""); setResults([]);
    router.push(`/company/${symbol}`);
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key !== "Enter") return;
    e.preventDefault();
    if (results.length > 0) {
      pick(results[0].symbol);
    } else if (query.trim()) {
      // No resolved candidates yet (still debouncing, or provider search came up
      // empty) — navigate straight there anyway. The company page resolves the
      // ticker itself server-side, so this still works for a brand-new symbol.
      pick(query.trim().toUpperCase());
    }
  }

  const dateStr = now.toLocaleDateString("en-IN", { weekday: "short", month: "short", day: "numeric" });
  const timeStr = now.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", hour12: true });

  return (
    <header
      className="sticky top-0 z-20 flex items-center gap-4 px-5 py-2.5"
      style={{
        background: "rgba(3,6,15,0.88)",
        backdropFilter: "blur(20px)",
        borderBottom: "1px solid rgba(255,255,255,0.05)",
        boxShadow: "0 1px 0 rgba(255,255,255,0.03)",
      }}
    >
      {/* Global ticker search */}
      <div ref={ref} className="relative flex-1 max-w-sm">
        <div
          className="relative flex items-center"
          style={{
            borderRadius: "10px",
            border: focused
              ? "1px solid rgba(59,130,246,0.6)"
              : "1px solid rgba(255,255,255,0.15)",
            background: focused
              ? "rgba(59,130,246,0.08)"
              : "rgba(0,0,0,0.4)",
            transition: "all 0.3s ease",
            boxShadow: focused ? "0 0 0 4px rgba(59,130,246,0.15), 0 0 25px rgba(59,130,246,0.15)" : "none",
          }}
        >
          <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" style={{ color: "var(--text-muted)" }} />
          <input
            ref={inputRef}
            id="global-ticker-search"
            type="text"
            value={query}
            onChange={(e) => handleInput(e.target.value)}
            onKeyDown={handleKeyDown}
            onFocus={() => { setFocused(true); if (results.length > 0) setOpen(true); }}
            onBlur={() => setFocused(false)}
            placeholder="Search ticker, company…"
            className="w-full py-2 pl-8 pr-16 text-sm bg-transparent outline-none"
            style={{
              color: "var(--text-primary)",
              fontFamily: "Inter, sans-serif",
              fontSize: "13px",
            }}
          />
          {/* Right decorations */}
          <div className="absolute right-2.5 top-1/2 -translate-y-1/2 flex items-center gap-1.5">
            {loading && <Loader2 size={12} className="animate-spin" style={{ color: "var(--text-muted)" }} />}
            {query && !loading && (
              <button
                onClick={() => { setQuery(""); setResults([]); setOpen(false); }}
                className="p-0.5 rounded transition-colors"
                style={{ color: "var(--text-muted)" }}
                onMouseEnter={(e) => e.currentTarget.style.color = "var(--text-primary)"}
                onMouseLeave={(e) => e.currentTarget.style.color = "var(--text-muted)"}
              >
                <X size={12} />
              </button>
            )}
            {!query && (
              <kbd
                className="flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[9px] font-mono font-semibold"
                style={{
                  background: "rgba(255,255,255,0.05)",
                  border: "1px solid rgba(255,255,255,0.1)",
                  color: "var(--text-muted)",
                }}
              >
                <Command size={8} /> K
              </kbd>
            )}
          </div>
        </div>

        {/* Dropdown */}
        {open && results.length > 0 && (
          <div
            className="absolute top-full left-0 right-0 mt-1.5 py-1 overflow-hidden fade-in-fast"
            style={{
              background: "rgba(5,9,18,0.98)",
              border: "1px solid rgba(59,130,246,0.18)",
              borderRadius: "12px",
              boxShadow: "0 20px 60px rgba(0,0,0,0.7), 0 0 0 1px rgba(255,255,255,0.04)",
              backdropFilter: "blur(20px)",
              zIndex: 50,
            }}
          >
            {results.slice(0, 8).map((c) => (
              <button
                key={c.symbol}
                onClick={() => pick(c.symbol)}
                className="w-full flex items-center gap-3 px-3.5 py-2.5 text-left transition-colors"
                onMouseEnter={(e) => e.currentTarget.style.background = "rgba(59,130,246,0.07)"}
                onMouseLeave={(e) => e.currentTarget.style.background = "transparent"}
              >
                <span
                  className="text-xs font-bold font-mono w-14 flex-shrink-0"
                  style={{ color: "var(--accent-light)" }}
                >
                  {c.symbol}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-xs truncate" style={{ color: "var(--text-secondary)" }}>{c.company_name ?? "—"}</p>
                  <p className="text-[10px]" style={{ color: "var(--text-muted)" }}>
                    {[c.exchange, c.sector].filter(Boolean).join(" · ")}
                  </p>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Right side */}
      <div className="flex items-center gap-3 ml-auto">
        {/* Date / time */}
        <div className="hidden md:flex flex-col items-end">
          <span className="text-[11px] font-semibold" style={{ color: "var(--text-secondary)" }}>{timeStr}</span>
          <span className="text-[9px]" style={{ color: "var(--text-muted)" }}>{dateStr}</span>
        </div>

        {/* Live chip */}
        <div
          className="flex items-center gap-1.5 px-2.5 py-1 rounded-full"
          style={{
            background: "rgba(34,197,94,0.08)",
            border: "1px solid rgba(34,197,94,0.2)",
          }}
        >
          <div className="live-dot" />
          <span className="text-[10px] font-semibold" style={{ color: "var(--green)" }}>Live</span>
        </div>
      </div>
    </header>
  );
}
