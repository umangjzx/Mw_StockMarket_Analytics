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

  useEffect(() => {
    if (!containerRef.current || !bars.length) return;

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

    const sorted = [...bars].sort(
      (a, b) => new Date(a.ts).getTime() - new Date(b.ts).getTime()
    );

    candleSeries.setData(
      sorted.map((b) => ({
        time: Math.floor(new Date(b.ts).getTime() / 1000) as UTCTimestamp,
        open: b.open,
        high: b.high,
        low: b.low,
        close: b.close,
      }))
    );

    volumeSeries.setData(
      sorted.map((b) => ({
        time: Math.floor(new Date(b.ts).getTime() / 1000) as UTCTimestamp,
        value: b.volume ?? 0,
        color: b.close >= b.open ? "rgba(34, 197, 94, 0.4)" : "rgba(239, 68, 68, 0.4)",
      }))
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
