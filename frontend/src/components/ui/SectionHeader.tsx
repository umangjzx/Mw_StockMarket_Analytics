"use client";

import { cn } from "@/lib/utils";
import type { LucideIcon } from "lucide-react";

// ── Icon sizing convention (lucide-react `size` prop) ───────────────────────
// Pick the closest match below for any new icon usage; don't introduce a new
// size without updating this comment. Enforcement is a convention, not a
// lint rule — appropriate for a solo project.
//
//   11  inline-badge   — icon inside a chip/badge/stat-chip, next to small text
//   12  micro          — dismiss/close buttons inside compact rows, table cells
//   13  button         — icon inside btn-ghost/btn-primary/btn-danger, inline actions
//   14  section-header — icon inside a SectionHeader's icon-container (the default)
//   16  emphasis       — a section header needing slightly more visual weight (sparing use)
//   20+ hero/display   — empty-state icons, large standalone icons, illustration-scale use
//
// Every icon-only interactive element (a button with no visible text label)
// must ship with an `aria-label` at the point of creation — not bolted on
// later. This applies to every shared component, not just SectionHeader.

type IconColor = "blue" | "green" | "purple" | "amber" | "red" | "teal";

interface SectionHeaderProps {
  icon: LucideIcon;
  iconColor?: IconColor;
  title: React.ReactNode; // usually a string, but supports e.g. an inline count badge
  action?: React.ReactNode; // right-aligned slot: refresh button, toggle, "View all" link
  className?: string;
}

export function SectionHeader({ icon: Icon, iconColor = "blue", title, action, className }: SectionHeaderProps) {
  return (
    <div className={cn("section-header", className)}>
      <div className="section-title">
        <div className={cn("icon-container", `icon-${iconColor}`)}>
          <Icon size={14} aria-hidden="true" />
        </div>
        {title}
      </div>
      {action}
    </div>
  );
}
