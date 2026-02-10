"use client"

import { useEffect, useState } from "react"
import { FileText, BarChart3, Target, TrendingUp } from "lucide-react"
import { useAuth } from "@/lib/auth-context"
import { getDashboardStats, type DashboardStats } from "@/lib/api"
import { DashboardLayout } from "@/components/layout/dashboard-layout"
import { Sidebar } from "@/components/layout/sidebar"
import { SummaryCard } from "@/components/ui/summary-card"

export default function DashboardPage() {
  const { token, isAuthenticated, isLoading } = useAuth()
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [error, setError] = useState("")

  useEffect(() => {
    if (!token) return

    getDashboardStats(token)
      .then(setStats)
      .catch(() => {
        // Fallback to zeros if the endpoint isn't available yet
        setStats({ total_resumes: 0, analyses_run: 0, avg_match_score: 0 })
      })
  }, [token])

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-muted/30">
        <p className="text-sm text-muted-foreground">Loading...</p>
      </div>
    )
  }

  if (!isAuthenticated) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-muted/30">
        <p className="text-sm text-muted-foreground">Redirecting...</p>
      </div>
    )
  }

  const displayStats = stats ?? { total_resumes: 0, analyses_run: 0, avg_match_score: 0 }

  return (
    <DashboardLayout sidebar={<Sidebar />}>
      <div className="mx-auto max-w-6xl space-y-8">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">
            Dashboard
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Overview of your hiring pipeline
          </p>
        </div>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <SummaryCard
            title="Resumes"
            subtitle="Total uploaded"
            stats={[
              {
                icon: FileText,
                label: "Total resumes",
                value: displayStats.total_resumes,
              },
            ]}
          />

          <SummaryCard
            title="Analyses"
            subtitle="Processing metrics"
            stats={[
              {
                icon: BarChart3,
                label: "Analyses run",
                value: displayStats.analyses_run,
              },
              {
                icon: TrendingUp,
                label: "Completion rate",
                value:
                  displayStats.total_resumes > 0
                    ? `${Math.round((displayStats.analyses_run / displayStats.total_resumes) * 100)}%`
                    : "—",
              },
            ]}
          />

          <SummaryCard
            title="Match Quality"
            subtitle="Candidate scoring"
            stats={[
              {
                icon: Target,
                label: "Avg match score",
                value:
                  displayStats.avg_match_score > 0
                    ? `${displayStats.avg_match_score}%`
                    : "—",
              },
            ]}
          />
        </div>
      </div>
    </DashboardLayout>
  )
}
