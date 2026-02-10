"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { LayoutDashboard, FileText, LogOut } from "lucide-react"
import { cn } from "@/lib/utils"
import { useAuth } from "@/lib/auth-context"

const navItems = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/dashboard/resumes", label: "Resumes", icon: FileText },
]

export function Sidebar() {
  const pathname = usePathname()
  const { logout } = useAuth()

  return (
    <div className="flex h-full flex-col">
      <div className="px-5 py-5">
        <Link
          href="/dashboard"
          className="group flex items-center gap-2.5"
        >
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-foreground text-background text-xs font-bold">
            F
          </div>
          <span className="text-sm font-semibold tracking-tight text-foreground">
            FairHire
          </span>
        </Link>
      </div>

      <nav className="flex-1 px-3 pt-2">
        <p className="mb-2 px-2.5 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground/50">
          Navigation
        </p>
        <div className="space-y-0.5">
          {navItems.map((item) => {
            const isActive =
              pathname === item.href ||
              (item.href !== "/dashboard" && pathname.startsWith(item.href))
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-[13px] font-medium transition-all duration-150",
                  isActive
                    ? "bg-foreground/[0.05] text-foreground shadow-[var(--shadow-xs)]"
                    : "text-muted-foreground hover:bg-foreground/[0.03] hover:text-foreground"
                )}
              >
                <item.icon className="h-4 w-4 shrink-0" />
                {item.label}
              </Link>
            )
          })}
        </div>
      </nav>

      <div className="border-t px-3 py-3">
        <button
          onClick={logout}
          className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-[13px] font-medium text-muted-foreground transition-all duration-150 hover:bg-foreground/[0.03] hover:text-foreground"
        >
          <LogOut className="h-4 w-4 shrink-0" />
          Sign out
        </button>
      </div>
    </div>
  )
}
