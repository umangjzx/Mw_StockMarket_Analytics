"use client";

interface TooltipPayloadItem {
  name?: string;
  value?: number | string;
  color?: string;
  fill?: string;
  payload?: any;
}

interface ChartTooltipProps {
  active?: boolean;
  label?: string;
  payload?: TooltipPayloadItem[];
  render?: (payload: TooltipPayloadItem[]) => React.ReactNode;
}

export function ChartTooltip({ active, label, payload, render }: ChartTooltipProps) {
  if (!active || !payload?.length) return null;
  return (
    <div className="tooltip" role="tooltip">
      {label && <p className="text-[11px] mb-1.5 font-semibold" style={{ color: "var(--text-muted)" }}>{label}</p>}
      {render
        ? render(payload)
        : payload.map((p, i) => (
            <p key={i} style={{ color: p.color ?? p.fill }} className="text-xs font-mono">
              {p.name}:{" "}
              <span className="font-semibold">
                {typeof p.value === "number" ? p.value.toFixed(1) : p.value}
              </span>
            </p>
          ))}
    </div>
  );
}
