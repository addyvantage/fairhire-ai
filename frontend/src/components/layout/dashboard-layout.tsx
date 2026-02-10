import { ReactNode } from "react"

export function DashboardLayout({
  sidebar,
  children,
}: {
  sidebar: ReactNode
  children: ReactNode
}) {
  return (
    <div className="flex min-h-screen bg-muted/30">
      <aside className="w-64 border-r bg-background">
        {sidebar}
      </aside>
      <main className="flex-1 p-8">{children}</main>
    </div>
  )
}
