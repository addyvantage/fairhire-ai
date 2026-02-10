"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import {
  LayoutDashboard,
  FileText,
  Briefcase,
  BarChart3,
  Settings,
  LogOut,
  PanelLeftClose,
  PanelLeftOpen,
} from "lucide-react"
import { motion } from "framer-motion"
import { cn } from "@/lib/utils"
import { useAuth } from "@/lib/auth-context"

const navItems = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/dashboard/resumes", label: "Resumes", icon: FileText },
  { href: "/dashboard/jobs", label: "Job Profiles", icon: Briefcase },
  { href: "/dashboard/analytics", label: "Analytics", icon: BarChart3 },
  { href: "/dashboard/settings", label: "Settings", icon: Settings },
]

export function Sidebar({
  collapsed,
  onToggle,
}: {
  collapsed: boolean
  onToggle: () => void
}) {
  const pathname = usePathname()
  const { logout } = useAuth()

  return (
    <div className="flex h-full flex-col">
      <div className="flex h-16 items-center justify-between border-b border-border/80 px-4">
        <Link href="/dashboard" className="group flex min-w-0 items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-primary text-xs font-bold text-primary-foreground">
            FH
          </div>
          {!collapsed && (
            <span className="truncate text-sm font-semibold tracking-tight text-foreground">
              FairHire AI
            </span>
          )}
        </Link>
        <button
          type="button"
          onClick={onToggle}
          className="rounded-lg p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground"
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? <PanelLeftOpen className="h-4 w-4" /> : <PanelLeftClose className="h-4 w-4" />}
        </button>
      </div>

      <nav className="flex-1 px-3 py-4">
        {!collapsed && (
          <p className="mb-3 px-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground/70">
            Workspace
          </p>
        )}
        <div className="space-y-1">
          {navItems.map((item) => {
            const isActive =
              pathname === item.href ||
              (item.href !== "/dashboard" && pathname.startsWith(item.href))
            return (
              <Link
                key={item.href}
                href={item.href}
                title={collapsed ? item.label : undefined}
                className={cn(
                  "relative flex items-center gap-2.5 rounded-xl px-3 py-2.5 text-sm font-medium",
                  collapsed && "justify-center px-0",
                  isActive
                    ? "bg-primary-soft text-primary shadow-[var(--shadow-xs)]"
                    : "text-muted-foreground hover:bg-muted hover:text-foreground"
                )}
              >
                {isActive && (
                  <motion.span
                    layoutId="sidebar-active"
                    className="absolute inset-0 -z-10 rounded-xl border border-indigo-200/70"
                    transition={{ type: "spring", stiffness: 460, damping: 38 }}
                  />
                )}
                <item.icon className="h-4 w-4 shrink-0" />
                {!collapsed && item.label}
              </Link>
            )
          })}
        </div>
      </nav>

      <div className="border-t border-border/80 px-3 py-3">
        <button
          onClick={logout}
          title={collapsed ? "Sign out" : undefined}
          className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-[13px] font-medium text-muted-foreground transition-all duration-150 hover:bg-foreground/[0.03] hover:text-foreground"
        >
          <LogOut className="h-4 w-4 shrink-0" />
          {!collapsed && "Sign out"}
        </button>
      </div>
    </div>
  )
}
