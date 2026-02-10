"use client"

import { X, CheckCircle2, AlertCircle } from "lucide-react"
import { motion, AnimatePresence } from "framer-motion"
import { useToast } from "@/components/ui/use-toast"
import { cn } from "@/lib/utils"

export function Toaster() {
  const { toasts, dismiss } = useToast()

  return (
    <div
      aria-live="polite"
      className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 w-80"
    >
      <AnimatePresence mode="popLayout">
        {toasts.map((toast) => (
          <motion.div
            key={toast.id}
            layout
            initial={{ opacity: 0, y: 8, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -4, scale: 0.96 }}
            transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
            className={cn(
              "rounded-xl border bg-background px-4 py-3 shadow-[var(--shadow-lg)]",
              toast.variant === "destructive" && "border-destructive/15 bg-destructive/[0.02]"
            )}
          >
            <div className="flex items-start gap-2.5">
              {toast.variant === "destructive" ? (
                <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-destructive" />
              ) : (
                <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-success" />
              )}
              <div className="flex-1 space-y-0.5">
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
                className="shrink-0 rounded-md p-0.5 text-muted-foreground/40 transition-colors duration-150 hover:text-foreground"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  )
}
