import { cn } from "@/lib/utils"
import type { LucideIcon } from "lucide-react"

interface StatItem {
  icon: LucideIcon
  label: string
  value: string | number
}

interface SummaryCardProps {
  title: string
  subtitle?: string
  stats: StatItem[]
}

export function SummaryCard({ title, subtitle, stats }: SummaryCardProps) {
  const primary = stats[0]
  const secondary = stats.slice(1)

  return (
    <div className="rounded-xl border bg-background p-5 shadow-[var(--shadow-xs)] transition-shadow duration-200 hover:shadow-[var(--shadow-sm)]">
      <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
        {title}
      </p>
      {subtitle && (
        <p className="mt-0.5 text-[11px] text-muted-foreground/60">{subtitle}</p>
      )}

      {primary && (
        <div className="mt-3 flex items-baseline gap-2">
          <span className="text-2xl font-semibold tracking-tight text-foreground tabular-nums">
            {primary.value}
          </span>
          <span className="text-xs text-muted-foreground">{primary.label}</span>
        </div>
      )}

      {secondary.length > 0 && (
        <div className="mt-3 space-y-1.5 border-t pt-3">
          {secondary.map((stat, index) => (
            <div
              key={index}
              className="flex items-center justify-between text-sm"
            >
              <div className="flex items-center gap-2 text-muted-foreground">
                <stat.icon className={cn("h-3.5 w-3.5")} />
                <span className="text-xs">{stat.label}</span>
              </div>
              <span className="text-xs font-medium text-foreground tabular-nums">
                {stat.value}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
