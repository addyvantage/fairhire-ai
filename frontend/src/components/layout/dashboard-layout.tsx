"use client"

import { ReactNode, useEffect, useState } from "react"
import { cn } from "@/lib/utils"
import { Sidebar } from "@/components/layout/sidebar"
import { TopBar } from "@/components/layout/top-bar"

const SIDEBAR_STORAGE_KEY = "fairhire_sidebar_collapsed"

export function DashboardLayout({
  title,
  description,
  actions,
  children,
}: {
  title: string
  description?: string
  actions?: ReactNode
  children: ReactNode
}) {
  const [collapsed, setCollapsed] = useState(false)
  const [hydrated, setHydrated] = useState(false)

  useEffect(() => {
    const stored = localStorage.getItem(SIDEBAR_STORAGE_KEY)
    if (stored) {
      setCollapsed(stored === "true")
    }
    setHydrated(true)
  }, [])

  useEffect(() => {
    if (!hydrated) return
    localStorage.setItem(SIDEBAR_STORAGE_KEY, String(collapsed))
  }, [collapsed, hydrated])

  return (
    <div className="min-h-screen bg-background">
      <div className="flex">
        <aside
          className={cn(
            "sticky top-0 z-30 h-screen shrink-0 border-r border-border/90 bg-card/85 backdrop-blur-xl transition-[width] duration-200",
            collapsed ? "w-[88px]" : "w-[252px]"
          )}
        >
          <Sidebar collapsed={collapsed} onToggle={() => setCollapsed((prev) => !prev)} />
        </aside>

        <div className="flex min-h-screen flex-1 flex-col">
          <TopBar title={title} description={description} actions={actions} />
          <main className="flex-1 px-6 py-6 lg:px-10 lg:py-8">{children}</main>
        </div>
      </div>
    </div>
  )
}
