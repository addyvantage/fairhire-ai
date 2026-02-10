import { ReactNode } from "react"
import { Bell } from "lucide-react"

export function TopBar({
  title,
  description,
  actions,
}: {
  title: string
  description?: string
  actions?: ReactNode
}) {
  return (
    <header className="sticky top-0 z-20 border-b border-border/90 bg-background/90 backdrop-blur-xl">
      <div className="flex h-[84px] items-center justify-between px-6 lg:px-10">
        <div className="min-w-0">
          <h1 className="truncate text-2xl font-semibold tracking-tight text-foreground">{title}</h1>
          {description && <p className="mt-1 text-sm text-muted-foreground">{description}</p>}
        </div>
        <div className="ml-6 flex shrink-0 items-center gap-3">
          {actions}
          <button
            type="button"
            className="inline-flex h-9 w-9 items-center justify-center rounded-full border border-border bg-card text-muted-foreground hover:text-foreground"
            aria-label="Notifications"
          >
            <Bell className="h-4 w-4" />
          </button>
          <div className="inline-flex h-9 w-9 items-center justify-center rounded-full bg-primary text-xs font-semibold text-primary-foreground">
            FH
          </div>
        </div>
      </div>
    </header>
  )
}
