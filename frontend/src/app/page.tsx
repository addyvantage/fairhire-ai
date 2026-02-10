"use client"

import { useEffect } from "react"
import { useRouter } from "next/navigation"
import { useAuth } from "@/lib/auth-context"

export default function HomePage() {
  const { isAuthenticated, isLoading } = useAuth()
  const router = useRouter()

  useEffect(() => {
    if (isLoading) return
    if (isAuthenticated) {
      router.replace("/dashboard")
    } else {
      router.replace("/login")
    }
  }, [isAuthenticated, isLoading, router])

  return (
    <div className="flex min-h-screen items-center justify-center bg-muted/30">
      <p className="text-sm text-muted-foreground">Redirecting...</p>
    </div>
  )
}
