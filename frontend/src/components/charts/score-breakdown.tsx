"use client"

import { motion } from "framer-motion"
import { transitions } from "@/lib/motion"
import { cn } from "@/lib/utils"

type ScoreBar = {
  label: string
  score: number
  weight?: string
  tone?: "primary" | "success" | "warning" | "destructive" | "neutral"
}

const toneClass: Record<NonNullable<ScoreBar["tone"]>, string> = {
  primary: "bg-primary",
  success: "bg-emerald-500",
  warning: "bg-amber-500",
  destructive: "bg-rose-500",
  neutral: "bg-slate-500",
}

export function ScoreBreakdown({ scores }: { scores: ScoreBar[] }) {
  return (
    <div className="space-y-4">
      {scores.map((item, index) => {
        const normalized = Math.max(0, Math.min(100, item.score))
        return (
          <div key={item.label} className="space-y-2">
            <div className="flex items-center justify-between gap-3">
              <p className="text-sm font-medium text-foreground">{item.label}</p>
              <div className="flex items-center gap-2">
                <p className="text-sm font-semibold tabular-nums text-foreground">
                  {item.score.toFixed(1)}%
                </p>
                {item.weight && <p className="text-xs text-muted-foreground">· {item.weight}</p>}
              </div>
            </div>
            <div className="h-2.5 w-full overflow-hidden rounded-full bg-muted">
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: `${normalized}%` }}
                transition={{ ...transitions.base, delay: index * 0.05 }}
                className={cn("h-full rounded-full", toneClass[item.tone ?? "primary"])}
              />
            </div>
          </div>
        )
      })}
    </div>
  )
}
