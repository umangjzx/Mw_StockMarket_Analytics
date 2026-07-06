"use client";

import { cn } from "@/lib/utils";

interface SkeletonProps { className?: string; style?: React.CSSProperties; }

export function Skeleton({ className, style }: SkeletonProps) {
  return <div className={cn("skeleton h-4 w-full", className)} style={style} />;
}

export function SkeletonCard({ rows = 4, className }: { rows?: number; className?: string }) {
  return (
    <div className={cn("glass-card p-5 space-y-3", className)}>
      <Skeleton className="h-5 w-2/5 rounded-lg" />
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className={`h-3 ${i % 2 === 0 ? "w-full" : "w-3/4"} rounded-md`} />
      ))}
    </div>
  );
}

export function SkeletonTable({ rows = 5 }: { rows?: number }) {
  return (
    <div className="space-y-px">
      <Skeleton className="h-9 w-full rounded-none" style={{ borderRadius: "10px 10px 0 0" } as any} />
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className="h-12 w-full rounded-none" />
      ))}
    </div>
  );
}
