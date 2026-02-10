"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import {
  ArrowRight,
  BarChart3,
  Briefcase,
  FileText,
  Sparkles,
  Target,
  TrendingUp,
} from "lucide-react"
import { motion } from "framer-motion"
import { useAuth } from "@/lib/auth-context"
import { DashboardStats, getDashboardStats } from "@/lib/api"
import { DashboardLayout } from "@/components/layout/dashboard-layout"
import { Button } from "@/components/ui/button"
import { EmptyState } from "@/components/ui/empty-state"
import { KpiCard } from "@/components/ui/kpi-card"
import { PageTransition } from "@/components/ui/page-transition"
import { SectionCard } from "@/components/ui/section-card"
import { Skeleton } from "@/components/ui/skeleton"
import { fadeUp, staggerContainer } from "@/lib/motion"

const EMPTY_STATS: DashboardStats = {
  total_resumes: 0,
  total_analyses: 0,
  completed_analyses: 0,
  avg_match_score: 0,
  completion_rate: 0,
  total_job_profiles: 0,
}

function DashboardSkeleton() {
  return (
    <DashboardLayout title="Dashboard" description="Executive overview of your hiring workflow">
      <div className="mx-auto w-full max-w-6xl space-y-6">
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
          {Array.from({ length: 5 }).map((_, index) => (
            <div key={index} className="surface-card space-y-3 p-5">
              <Skeleton className="h-3 w-24" />
              <Skeleton className="h-9 w-16" />
              <Skeleton className="h-3 w-28" />
            </div>
          ))}
        </div>
        <Skeleton className="h-64 w-full rounded-[var(--radius)]" />
      </div>
    </DashboardLayout>
  )
}

export default function DashboardPage() {
  const { token, isAuthenticated, isLoading } = useAuth()
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [loaded, setLoaded] = useState(false)
  const router = useRouter()

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.replace("/login")
    }
  }, [isLoading, isAuthenticated, router])

  useEffect(() => {
    if (!token) return
    getDashboardStats(token)
      .then((value) => setStats(value))
      .catch(() => setStats(EMPTY_STATS))
      .finally(() => setLoaded(true))
  }, [token])

  const snapshotSafe = stats ?? EMPTY_STATS
  const hasData = snapshotSafe.total_resumes > 0 || snapshotSafe.total_analyses > 0
  const activity = [
    `${snapshotSafe.total_resumes} resume${snapshotSafe.total_resumes === 1 ? "" : "s"} uploaded`,
    `${snapshotSafe.total_job_profiles} job profile${snapshotSafe.total_job_profiles === 1 ? "" : "s"} configured`,
    `${snapshotSafe.completed_analyses} completed analys${snapshotSafe.completed_analyses === 1 ? "is" : "es"}`,
    ...(snapshotSafe.avg_match_score > 0
      ? [`Average candidate fit is ${snapshotSafe.avg_match_score}%`]
      : []),
  ]

  if (isLoading || !isAuthenticated) return <DashboardSkeleton />

  return (
    <DashboardLayout
      title="Dashboard"
      description="Executive overview of resume throughput and candidate quality."
      actions={
        <Button asChild size="sm">
          <Link href="/dashboard/resumes" className="gap-2">
            Upload Resume
            <ArrowRight className="h-4 w-4" />
          </Link>
        </Button>
      }
    >
      <PageTransition className="mx-auto w-full max-w-6xl">
        <motion.section
          variants={staggerContainer(0.06)}
          initial="hidden"
          animate={loaded ? "show" : "hidden"}
          className="grid gap-4 md:grid-cols-2 xl:grid-cols-5"
        >
          <motion.div variants={fadeUp()}>
            <KpiCard
              label="Total Resumes"
              value={snapshotSafe.total_resumes}
              helper="Candidates imported"
              icon={FileText}
            />
          </motion.div>
          <motion.div variants={fadeUp()}>
            <KpiCard
              label="Total Analyses"
              value={snapshotSafe.total_analyses}
              helper={`${snapshotSafe.completed_analyses} complete`}
              icon={BarChart3}
            />
          </motion.div>
          <motion.div variants={fadeUp()}>
            <KpiCard
              label="Job Profiles"
              value={snapshotSafe.total_job_profiles}
              helper="Template + custom roles"
              icon={Briefcase}
            />
          </motion.div>
          <motion.div variants={fadeUp()}>
            <KpiCard
              label="Avg Match Score"
              value={snapshotSafe.avg_match_score > 0 ? `${snapshotSafe.avg_match_score}%` : "—"}
              helper="Across completed analyses"
              icon={Target}
            />
          </motion.div>
          <motion.div variants={fadeUp()}>
            <KpiCard
              label="Completion Rate"
              value={snapshotSafe.completion_rate > 0 ? `${snapshotSafe.completion_rate}%` : "—"}
              helper="Queue to completed"
              icon={TrendingUp}
              tone="positive"
            />
          </motion.div>
        </motion.section>

        {!hasData ? (
          <EmptyState
            icon={<Sparkles className="h-5 w-5" />}
            title="Your workspace is ready"
            description="Upload your first resume and run an analysis to populate your executive dashboard."
            action={
              <Button asChild>
                <Link href="/dashboard/resumes">Start with resumes</Link>
              </Button>
            }
          />
        ) : (
          <SectionCard
            title="Recent Activity"
            description="A quick pulse on what happened in your pipeline."
            action={
              <Button variant="outline" size="sm" asChild>
                <Link href="/dashboard/resumes">Review resumes</Link>
              </Button>
            }
          >
            <div className="grid gap-3 md:grid-cols-3">
              {activity.map((item) => (
                <div key={item} className="rounded-xl border border-border/80 bg-muted/40 px-4 py-3">
                  <p className="text-sm text-foreground">{item}</p>
                </div>
              ))}
            </div>
          </SectionCard>
        )}
      </PageTransition>
    </DashboardLayout>
  )
}
