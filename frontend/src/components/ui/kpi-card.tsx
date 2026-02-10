import { LucideIcon } from "lucide-react"
import { cn } from "@/lib/utils"

export function KpiCard({
  label,
  value,
  helper,
  icon: Icon,
  tone = "default",
}: {
  label: string
  value: string | number
  helper?: string
  icon: LucideIcon
  tone?: "default" | "positive"
}) {
  return (
    <div className="surface-card p-5 transition-transform duration-200 hover:-translate-y-0.5 hover:shadow-[var(--shadow-sm)]">
      <div className="mb-4 flex items-center justify-between">
        <p className="text-xs font-semibold uppercase tracking-[0.08em] text-muted-foreground">{label}</p>
        <div
          className={cn(
            "flex h-8 w-8 items-center justify-center rounded-lg",
            tone === "positive" ? "bg-emerald-50 text-emerald-600" : "bg-muted text-muted-foreground"
          )}
        >
          <Icon className="h-4 w-4" />
        </div>
      </div>
      <p className="text-3xl font-semibold tracking-tight text-foreground tabular-nums">{value}</p>
      {helper && <p className="mt-2 text-sm text-muted-foreground">{helper}</p>}
    </div>
  )
}
