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
      <aside className="sticky top-0 h-screen w-56 shrink-0 border-r bg-background">
        {sidebar}
      </aside>
      <main className="flex-1 px-8 py-8 lg:px-12">{children}</main>
    </div>
  )
}
