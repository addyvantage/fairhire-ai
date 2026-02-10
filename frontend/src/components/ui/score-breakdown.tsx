"use client"

import { motion } from "framer-motion"

type SubScore = {
  label: string
  score: number
  weight: string
  color: string
}

type Props = {
  scores: SubScore[]
}

export function ScoreBreakdown({ scores }: Props) {
  return (
    <div className="space-y-3">
      {scores.map((item, i) => (
        <div key={item.label} className="space-y-1.5">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-foreground">
              {item.label}
            </span>
            <div className="flex items-center gap-2">
              <span className="text-xs tabular-nums font-medium text-foreground">
                {item.score.toFixed(1)}%
              </span>
              <span className="text-[10px] text-muted-foreground/60">
                {item.weight}
              </span>
            </div>
          </div>
          <div className="h-2 w-full rounded-full bg-muted/40 overflow-hidden">
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: `${Math.min(100, Math.max(0, item.score))}%` }}
              transition={{ duration: 0.6, delay: i * 0.1, ease: [0.16, 1, 0.3, 1] }}
              className={`h-full rounded-full ${item.color}`}
            />
          </div>
        </div>
      ))}
    </div>
  )
}
