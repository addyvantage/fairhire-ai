import { cva } from "class-variance-authority"
import { cn } from "@/lib/utils"

const pillVariants = cva(
  "inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium capitalize",
  {
    variants: {
      tone: {
        neutral: "bg-muted text-muted-foreground",
        queued: "bg-slate-100 text-slate-600",
        processing: "bg-indigo-50 text-indigo-700",
        completed: "bg-emerald-50 text-emerald-700",
        failed: "bg-rose-50 text-rose-700",
      },
    },
    defaultVariants: {
      tone: "neutral",
    },
  }
)

export function StatusPill({
  status,
  className,
}: {
  status: "queued" | "processing" | "completed" | "failed"
  className?: string
}) {
  return <span className={cn(pillVariants({ tone: status }), className)}>{status}</span>
}
