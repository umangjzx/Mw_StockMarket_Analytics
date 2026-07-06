"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard, Building2, Video, Search,
  MessageSquare, BarChart2, Bookmark, Settings,
  ChevronLeft, ChevronRight, TrendingUp, Activity,
  Zap, Tv,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useState } from "react";
import { Modal } from "@/components/ui/Modal";
import { ProcessVideoForm } from "@/components/ProcessVideoForm";

const NAV_MAIN = [
  { href: "/",          icon: LayoutDashboard, label: "Dashboard",  color: "text-blue-400" },
  { href: "/videos",    icon: Video,           label: "Videos",     color: "text-red-400" },
  { href: "/search",    icon: Search,          label: "Search",     color: "text-slate-400" },
  { href: "/chat",      icon: MessageSquare,   label: "AI Chat",    color: "text-green-400" },
];
const NAV_TOOLS = [
  { href: "/analytics", icon: BarChart2,  label: "Analytics",   color: "text-purple-400" },
  { href: "/channels",  icon: Tv,         label: "Channels",    color: "text-red-400" },
  { href: "/watchlist", icon: Bookmark,   label: "Watchlist",   color: "text-amber-400" },
  { href: "/admin",     icon: Settings,   label: "Admin",       color: "text-slate-500" },
];

export function Sidebar() {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);
  const [showProcessModal, setShowProcessModal] = useState(false);

  const renderNav = (items: typeof NAV_MAIN) =>
    items.map(({ href, icon: Icon, label, color }) => {
      const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
      return (
        <Link
          key={href}
          href={href}
          title={collapsed ? label : undefined}
          className={cn(
            "sidebar-item hover:bg-white/[0.04]",
            active && "active bg-white/[0.08] shadow-inner border border-white/5",
            collapsed && "justify-center px-0",
          )}
        >
          <Icon
            size={16}
            className={cn("flex-shrink-0 transition-colors", active ? "text-blue-400" : color)}
          />
          {!collapsed && <span className="truncate">{label}</span>}
        </Link>
      );
    });

  return (
    <aside
      className={cn(
        "flex flex-col h-screen sticky top-0 transition-all duration-300 z-30",
        "border-r",
        collapsed ? "w-[60px]" : "w-[220px]",
      )}
      style={{
        background: "linear-gradient(180deg, rgba(7,13,26,0.98) 0%, rgba(5,9,18,0.98) 100%)",
        borderColor: "rgba(255,255,255,0.05)",
        backdropFilter: "blur(20px)",
      }}
    >
      {/* Logo */}
      <div className={cn(
        "flex items-center gap-3 px-4 py-5",
        "border-b",
        collapsed && "justify-center px-3",
      )}
        style={{ borderColor: "rgba(255,255,255,0.05)" }}
      >
        {/* Logo mark */}
        <div
          className="relative w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0"
          style={{
            background: "linear-gradient(135deg, #1d4ed8, #3b82f6)",
            boxShadow: "0 0 16px rgba(59,130,246,0.45), inset 0 1px 0 rgba(255,255,255,0.15)",
          }}
        >
          <TrendingUp size={15} className="text-white" strokeWidth={2.5} />
          {/* Animated ring */}
          <span
            className="absolute inset-0 rounded-xl"
            style={{
              border: "1px solid rgba(59,130,246,0.4)",
              animation: "pulse-blue 3s infinite",
            }}
          />
        </div>

        {!collapsed && (
          <div className="min-w-0">
            <p
              className="text-sm font-black leading-none tracking-tight"
              style={{
                background: "linear-gradient(135deg, #e8edf5, #93c5fd)",
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
                backgroundClip: "text",
              }}
            >
              MW Analytics
            </p>
            <p className="text-[10px] leading-none mt-0.5 truncate" style={{ color: "var(--text-muted)" }}>
              AI Market Intelligence
            </p>
          </div>
        )}
      </div>

      {/* Process Video Quick Action */}
      <div className="px-3 py-2">
        <button
          onClick={() => setShowProcessModal(true)}
          title={collapsed ? "Process YouTube Video" : undefined}
          className={cn(
            "w-full flex items-center gap-2 px-3 py-2 rounded-lg transition-all text-xs",
            collapsed && "justify-center px-0",
          )}
          style={{
            background: "rgba(244,63,94,0.08)",
            border: "1px solid rgba(244,63,94,0.2)",
            color: "var(--red-light)"
          }}
        >
          <Zap size={14} className="flex-shrink-0" />
          {!collapsed && <span className="font-semibold truncate">Process Video</span>}
        </button>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-2 py-3 space-y-0.5 overflow-y-auto">
        {/* Main */}
        {renderNav(NAV_MAIN)}

        {/* Separator */}
        <div className="py-2 px-3">
          <div
            className="flex items-center gap-2"
            style={{ borderTop: "1px solid rgba(255,255,255,0.04)" }}
          >
            {!collapsed && (
              <span
                className="text-[9px] font-bold uppercase tracking-widest pt-2"
                style={{ color: "var(--text-dim)" }}
              >
                Tools
              </span>
            )}
          </div>
        </div>

        {/* Tools */}
        {renderNav(NAV_TOOLS)}
      </nav>

      {/* Bottom: status + collapse */}
      <div className="px-2 pb-4 space-y-2">
        {/* Live status chip */}
        {!collapsed && (
          <div
            className="flex items-center gap-2 px-3 py-2 rounded-lg"
            style={{
              background: "rgba(34,197,94,0.06)",
              border: "1px solid rgba(34,197,94,0.15)",
            }}
          >
            <div className="live-dot flex-shrink-0" />
            <div className="min-w-0 flex-1">
              <p className="text-[10px] font-semibold text-green-400 leading-none">System Live</p>
              <p className="text-[9px] mt-0.5 truncate" style={{ color: "var(--text-muted)" }}>
                All services healthy
              </p>
            </div>
          </div>
        )}

        {/* Collapse toggle */}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className={cn(
            "w-full flex items-center gap-2 px-3 py-2 rounded-lg transition-all text-xs",
            collapsed && "justify-center px-0",
          )}
          style={{ color: "var(--text-muted)" }}
          onMouseEnter={(e) => { e.currentTarget.style.color = "var(--text-secondary)"; e.currentTarget.style.background = "rgba(255,255,255,0.04)"; }}
          onMouseLeave={(e) => { e.currentTarget.style.color = "var(--text-muted)"; e.currentTarget.style.background = "transparent"; }}
        >
          {collapsed
            ? <ChevronRight size={14} />
            : <><ChevronLeft size={14} /><span>Collapse</span></>
          }
        </button>
      </div>

      {showProcessModal && (
        <Modal onClose={() => setShowProcessModal(false)} title="Process YouTube Video">
          <ProcessVideoForm />
        </Modal>
      )}
    </aside>
  );
}
