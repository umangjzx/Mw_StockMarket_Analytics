"use client";

import { useEffect, useRef } from "react";
import {
  createChart,
  CandlestickSeries,
  HistogramSeries,
  ColorType,
  type UTCTimestamp,
} from "lightweight-charts";

interface Bar {
  ts: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number | null;
}

export function CandlestickChart({ bars, height = 260 }: { bars: Bar[]; height?: number }) {
  const containerRef = useRef<HTMLDivElement>(null);

  const isFiniteNumber = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);

  useEffect(() => {
    // Illiquid/dual-listed tickers (e.g. BSE-only small caps) can return bars
    // with null OHLC on days with no trades — lightweight-charts throws a
    // hard assertion error on any non-number value, so drop those bars.
    const clean = bars.filter(
      (b) => isFiniteNumber(b.open) && isFiniteNumber(b.high) && isFiniteNumber(b.low) && isFiniteNumber(b.close)
    );
    if (!containerRef.current || !clean.length) return;

    const chart = createChart(containerRef.current, {
      height,
      width: containerRef.current.clientWidth,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#64748b",
        fontSize: 10,
      },
      grid: {
        vertLines: { color: "rgba(148, 163, 184, 0.08)" },
        horzLines: { color: "rgba(148, 163, 184, 0.08)" },
      },
      rightPriceScale: { borderColor: "rgba(148, 163, 184, 0.15)" },
      timeScale: {
        borderColor: "rgba(148, 163, 184, 0.15)",
        timeVisible: true,
        secondsVisible: false,
      },
    });

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: "#22c55e",
      downColor: "#ef4444",
      borderVisible: false,
      wickUpColor: "#22c55e",
      wickDownColor: "#ef4444",
    });

    const volumeSeries = chart.addSeries(HistogramSeries, {
      priceFormat: { type: "volume" },
      priceScaleId: "volume",
    });
    chart.priceScale("volume").applyOptions({
      scaleMargins: { top: 0.82, bottom: 0 },
    });

    const sorted = [...clean].sort(
      (a, b) => new Date(a.ts).getTime() - new Date(b.ts).getTime()
    );

    // lightweight-charts also asserts on duplicate/non-ascending timestamps —
    // collapse same-second bars (last one wins) after flooring to seconds.
    const byTime = new Map<UTCTimestamp, typeof sorted[number]>();
    for (const b of sorted) {
      byTime.set(Math.floor(new Date(b.ts).getTime() / 1000) as UTCTimestamp, b);
    }
    const times = [...byTime.keys()].sort((a, b) => a - b);

    candleSeries.setData(
      times.map((time) => {
        const b = byTime.get(time)!;
        return { time, open: b.open, high: b.high, low: b.low, close: b.close };
      })
    );

    volumeSeries.setData(
      times.map((time) => {
        const b = byTime.get(time)!;
        return {
          time,
          value: b.volume ?? 0,
          color: b.close >= b.open ? "rgba(34, 197, 94, 0.4)" : "rgba(239, 68, 68, 0.4)",
        };
      })
    );

    chart.timeScale().fitContent();

    const resizeObserver = new ResizeObserver((entries) => {
      const { width } = entries[0].contentRect;
      chart.applyOptions({ width });
    });
    resizeObserver.observe(containerRef.current);

    return () => {
      resizeObserver.disconnect();
      chart.remove();
    };
  }, [bars, height]);

  if (!bars.length) return null;

  return <div ref={containerRef} className="w-full" />;
}
