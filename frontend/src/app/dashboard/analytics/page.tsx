"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { BarChart3, LineChart, Sparkles, Target } from "lucide-react"
import { useAuth } from "@/lib/auth-context"
import { DashboardStats, getDashboardStats } from "@/lib/api"
import { DashboardLayout } from "@/components/layout/dashboard-layout"
import { EmptyState } from "@/components/ui/empty-state"
import { KpiCard } from "@/components/ui/kpi-card"
import { PageTransition } from "@/components/ui/page-transition"
import { Skeleton } from "@/components/ui/skeleton"

const EMPTY_STATS: DashboardStats = {
  total_resumes: 0,
  total_analyses: 0,
  completed_analyses: 0,
  avg_match_score: 0,
  completion_rate: 0,
  total_job_profiles: 0,
}

function AnalyticsSkeleton() {
  return (
    <DashboardLayout title="Analytics" description="Performance and quality trends across your hiring funnel.">
      <div className="mx-auto w-full max-w-6xl space-y-6">
        <div className="grid gap-4 md:grid-cols-3">
          <Skeleton className="h-32 rounded-[var(--radius)]" />
          <Skeleton className="h-32 rounded-[var(--radius)]" />
          <Skeleton className="h-32 rounded-[var(--radius)]" />
        </div>
        <Skeleton className="h-72 rounded-[var(--radius)]" />
      </div>
    </DashboardLayout>
  )
}

export default function AnalyticsPage() {
  const { token, isAuthenticated, isLoading } = useAuth()
  const router = useRouter()
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [loaded, setLoaded] = useState(false)

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.replace("/login")
    }
  }, [isLoading, isAuthenticated, router])

  useEffect(() => {
    if (!token) return
    getDashboardStats(token)
      .then((result) => setStats(result))
      .catch(() => setStats(EMPTY_STATS))
      .finally(() => setLoaded(true))
  }, [token])

  if (isLoading || !isAuthenticated || !loaded) return <AnalyticsSkeleton />

  const snapshot = stats ?? EMPTY_STATS
  const hasData = snapshot.completed_analyses > 0

  return (
    <DashboardLayout title="Analytics" description="Performance and quality trends across your hiring funnel.">
      <PageTransition className="mx-auto w-full max-w-6xl">
        <div className="grid gap-4 md:grid-cols-3">
          <KpiCard
            label="Completed Analyses"
            value={snapshot.completed_analyses}
            helper="Evaluations finalized"
            icon={BarChart3}
          />
          <KpiCard
            label="Avg Match Score"
            value={snapshot.avg_match_score > 0 ? `${snapshot.avg_match_score}%` : "—"}
            helper="Candidate-role fit quality"
            icon={Target}
          />
          <KpiCard
            label="Completion Rate"
            value={snapshot.completion_rate > 0 ? `${snapshot.completion_rate}%` : "—"}
            helper="Pipeline processing efficiency"
            icon={LineChart}
          />
        </div>

        {!hasData ? (
          <EmptyState
            icon={<Sparkles className="h-5 w-5" />}
            title="Analytics will appear as analyses complete"
            description="Run a few targeted analyses and this page will populate with trend-level performance insights."
          />
        ) : (
          <section className="surface-card p-6">
            <h2 className="text-lg font-semibold text-foreground">Executive Insights</h2>
            <p className="mt-2 text-sm text-muted-foreground">
              Candidate fit is averaging <strong className="text-foreground">{snapshot.avg_match_score}%</strong>{" "}
              across <strong className="text-foreground">{snapshot.completed_analyses}</strong> completed analyses.
              Analysis throughput is currently at{" "}
              <strong className="text-foreground">{snapshot.completion_rate}%</strong>.
            </p>
          </section>
        )}
      </PageTransition>
    </DashboardLayout>
  )
}
