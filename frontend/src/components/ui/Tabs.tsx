"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";

interface Tab { id: string; label: string; }

interface TabsProps {
  tabs: Tab[];
  defaultTab?: string;
  onChange?: (id: string) => void;
  children: (activeTab: string) => React.ReactNode;
  className?: string;
}

export function Tabs({ tabs, defaultTab, onChange, children, className }: TabsProps) {
  const [active, setActive] = useState(defaultTab ?? tabs[0]?.id);

  function handleChange(id: string) {
    setActive(id);
    onChange?.(id);
  }

  return (
    <div className={cn("flex flex-col gap-0", className)}>
      <div className="flex overflow-x-auto border-b border-white/5 gap-0 scrollbar-none">
        {tabs.map((t) => (
          <button
            key={t.id}
            onClick={() => handleChange(t.id)}
            className={cn(
              "px-4 py-3 text-xs font-semibold transition-all duration-150 whitespace-nowrap",
              active === t.id ? "tab-active" : "tab-inactive",
            )}
          >
            {t.label}
          </button>
        ))}
      </div>
      <div className="pt-5">{children(active)}</div>
    </div>
  );
}
