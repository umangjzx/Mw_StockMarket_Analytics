"use client";

import Link from "next/link";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

interface TickerChipProps {
  symbol: string;
  href?: string; // if omitted, the chip is not a link
  sublabel?: React.ReactNode; // e.g. price + change, sentiment badge, mention count
  onRemove?: (symbol: string) => void;
  className?: string;
}

export function TickerChip({ symbol, href, sublabel, onRemove, className }: TickerChipProps) {
  const content = (
    <>
      {onRemove && (
        <button
          type="button"
          aria-label={`Remove ${symbol} from recently viewed`}
          onClick={(e) => { e.preventDefault(); e.stopPropagation(); onRemove(symbol); }}
          className="absolute top-1.5 right-1.5 opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded hover:bg-red-500/10 text-muted-fg hover:text-red-400"
        >
          <X size={11} />
        </button>
      )}
      <p className="font-mono font-bold text-sm group-hover:text-blue-400 transition-colors text-foreground">
        {symbol}
      </p>
      {sublabel}
    </>
  );

  const classes = cn(
    "glass-card-hover relative flex-shrink-0 w-[150px] p-3 rounded-xl border border-white/5 group",
    className,
  );

  if (href) {
    return (
      <Link href={href} className={classes}>
        {content}
      </Link>
    );
  }
  return <div className={classes}>{content}</div>;
}
