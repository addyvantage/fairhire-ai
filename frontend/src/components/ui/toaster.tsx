"use client"

import { X } from "lucide-react"
import { useToast } from "@/components/ui/use-toast"
import { cn } from "@/lib/utils"

export function Toaster() {
  const { toasts, dismiss } = useToast()

  if (toasts.length === 0) return null

  return (
    <div aria-live="polite" className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 w-80">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className={cn(
            "rounded-lg border bg-background px-4 py-3 shadow-lg animate-in",
            toast.variant === "destructive" && "border-destructive/20 bg-destructive/5"
          )}
        >
          <div className="flex items-start justify-between gap-2">
            <div className="space-y-0.5">
              <p
                className={cn(
                  "text-sm font-medium",
                  toast.variant === "destructive"
                    ? "text-destructive"
                    : "text-foreground"
                )}
              >
                {toast.title}
              </p>
              {toast.description && (
                <p className="text-xs text-muted-foreground">{toast.description}</p>
              )}
            </div>
            <button
              onClick={() => dismiss(toast.id)}
              className="shrink-0 rounded-md p-0.5 text-muted-foreground/60 transition-colors duration-150 hover:text-foreground"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      ))}
    </div>
  )
}
