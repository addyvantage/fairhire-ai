import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
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
  return (
    <Card className="border-border bg-background">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">
          {title}
        </CardTitle>
        {subtitle && (
          <p className="text-xs text-muted-foreground">{subtitle}</p>
        )}
      </CardHeader>
      <CardContent className="space-y-3">
        {stats.map((stat, index) => (
          <div
            key={index}
            className="flex items-center justify-between text-sm"
          >
            <div className="flex items-center gap-2 text-muted-foreground">
              <stat.icon className="h-4 w-4" />
              <span>{stat.label}</span>
            </div>
            <span className="font-medium text-foreground">
              {stat.value}
            </span>
          </div>
        ))}
      </CardContent>
    </Card>
  )
}
