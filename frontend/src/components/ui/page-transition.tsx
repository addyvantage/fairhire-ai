"use client"

import { motion } from "framer-motion"
import { pageEnter } from "@/lib/motion"
import { cn } from "@/lib/utils"

export function PageTransition({
  children,
  className,
}: {
  children: React.ReactNode
  className?: string
}) {
  return (
    <motion.div
      variants={pageEnter}
      initial="hidden"
      animate="show"
      className={cn("space-y-6", className)}
    >
      {children}
    </motion.div>
  )
}
