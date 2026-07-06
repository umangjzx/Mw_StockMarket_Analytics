"use client";

import { cn } from "@/lib/utils";
import type { LucideIcon } from "lucide-react";

interface StatChipProps {
  icon?: LucideIcon;
  iconColor?: string; // CSS color value or var(), applied to the icon only
  label: string;
  value: React.ReactNode;
  valueColor?: string; // defaults to var(--text-primary)
  className?: string;
}

export function StatChip({ icon: Icon, iconColor, label, value, valueColor, className }: StatChipProps) {
  return (
    <div className={cn("stat-chip", className)}>
      {Icon && <Icon size={11} style={{ color: iconColor ?? "var(--text-muted)" }} aria-hidden="true" />}
      <span style={{ color: "var(--text-muted)" }}>{label}</span>
      <span className="chip-value" style={{ color: valueColor ?? "var(--text-primary)" }}>{value}</span>
    </div>
  );
}
