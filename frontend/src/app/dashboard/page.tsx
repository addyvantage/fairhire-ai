"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { FileText, BarChart3, Target, TrendingUp } from "lucide-react"
import { useAuth } from "@/lib/auth-context"
import { getDashboardStats, type DashboardStats } from "@/lib/api"
import { DashboardLayout } from "@/components/layout/dashboard-layout"
import { Sidebar } from "@/components/layout/sidebar"
import { SummaryCard } from "@/components/ui/summary-card"
import { Skeleton } from "@/components/ui/skeleton"

function DashboardSkeleton() {
  return (
    <DashboardLayout sidebar={<Sidebar />}>
      <div className="mx-auto max-w-6xl space-y-8">
        <div className="space-y-2">
          <Skeleton className="h-7 w-32" />
          <Skeleton className="h-4 w-56" />
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="rounded-lg border bg-background p-6 space-y-4">
              <Skeleton className="h-3 w-20" />
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-3/4" />
            </div>
          ))}
        </div>
      </div>
    </DashboardLayout>
  )
}

export default function DashboardPage() {
  const { token, isAuthenticated, isLoading } = useAuth()
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const router = useRouter()

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.replace("/login")
    }
  }, [isLoading, isAuthenticated, router])

  useEffect(() => {
    if (!token) return

    getDashboardStats(token)
      .then(setStats)
      .catch(() => {
        setStats({ total_resumes: 0, analyses_run: 0, avg_match_score: 0 })
      })
  }, [token])

  if (isLoading || !isAuthenticated) {
    return <DashboardSkeleton />
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
