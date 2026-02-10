"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { FileText, BarChart3, Target, TrendingUp, Briefcase, ArrowRight, Play } from "lucide-react"
import { motion } from "framer-motion"
import { useAuth } from "@/lib/auth-context"
import { getDashboardStats, type DashboardStats } from "@/lib/api"
import { DashboardLayout } from "@/components/layout/dashboard-layout"
import { Sidebar } from "@/components/layout/sidebar"
import { SummaryCard } from "@/components/ui/summary-card"
import { Skeleton } from "@/components/ui/skeleton"

function DashboardSkeleton() {
  return (
    <DashboardLayout sidebar={<Sidebar />}>
      <div className="mx-auto max-w-5xl space-y-8">
        <div className="space-y-2">
          <Skeleton className="h-7 w-32" />
          <Skeleton className="h-4 w-56" />
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="rounded-xl border bg-background p-5 space-y-3">
              <Skeleton className="h-3 w-20" />
              <Skeleton className="h-7 w-16" />
            </div>
          ))}
        </div>
      </div>
    </DashboardLayout>
  )
}

const EMPTY_STATS: DashboardStats = {
  total_resumes: 0,
  total_analyses: 0,
  completed_analyses: 0,
  avg_match_score: 0,
  completion_rate: 0,
  total_job_profiles: 0,
}

const stagger = {
  hidden: {},
  show: { transition: { staggerChildren: 0.06 } },
}
const fadeUp = {
  hidden: { opacity: 0, y: 10 },
  show: { opacity: 1, y: 0, transition: { duration: 0.35, ease: [0.16, 1, 0.3, 1] as const } },
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
      .then((data) => {
        setStats(data)
        setLoaded(true)
      })
      .catch(() => {
        setStats(EMPTY_STATS)
        setLoaded(true)
      })
  }, [token])

  if (isLoading || !isAuthenticated) {
    return <DashboardSkeleton />
  }

  const s = stats ?? EMPTY_STATS
  const isEmpty = s.total_resumes === 0 && s.completed_analyses === 0
  const hasResumesButNoAnalyses = s.total_resumes > 0 && s.completed_analyses === 0

  return (
    <DashboardLayout sidebar={<Sidebar />}>
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
        className="mx-auto max-w-5xl space-y-8"
      >
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-foreground">
            Dashboard
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Overview of your hiring pipeline
          </p>
        </div>

        <motion.div
          variants={stagger}
          initial="hidden"
          animate={loaded ? "show" : "hidden"}
          className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5"
        >
          <motion.div variants={fadeUp}>
            <SummaryCard
              title="Resumes"
              subtitle="Total uploaded"
              stats={[
                {
                  icon: FileText,
                  label: "total",
                  value: s.total_resumes,
                },
              ]}
            />
          </motion.div>

          <motion.div variants={fadeUp}>
            <SummaryCard
              title="Analyses"
              subtitle="Completed"
              stats={[
                {
                  icon: BarChart3,
                  label: "completed",
                  value: s.completed_analyses,
                },
              ]}
            />
          </motion.div>

          <motion.div variants={fadeUp}>
            <SummaryCard
              title="Completion"
              subtitle="Analysis rate"
              stats={[
                {
                  icon: TrendingUp,
                  label: "rate",
                  value:
                    s.completion_rate > 0
                      ? `${s.completion_rate}%`
                      : "—",
                },
              ]}
            />
          </motion.div>

          <motion.div variants={fadeUp}>
            <SummaryCard
              title="Match Quality"
              subtitle="Average score"
              stats={[
                {
                  icon: Target,
                  label: "avg score",
                  value:
                    s.avg_match_score > 0
                      ? `${s.avg_match_score}%`
                      : "—",
                },
              ]}
            />
          </motion.div>

          <motion.div variants={fadeUp}>
            <SummaryCard
              title="Job Profiles"
              subtitle="Available"
              stats={[
                {
                  icon: Briefcase,
                  label: "profiles",
                  value: s.total_job_profiles,
                },
              ]}
            />
          </motion.div>
        </motion.div>

        {loaded && isEmpty && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.25 }}
            className="rounded-xl border border-dashed bg-muted/20 px-6 py-12 text-center"
          >
            <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-muted/60">
              <FileText className="h-5 w-5 text-muted-foreground/60" />
            </div>
            <p className="text-sm font-medium text-foreground/80">
              Get started by uploading a resume
            </p>
            <p className="mt-1 text-sm text-muted-foreground">
              Your pipeline metrics will appear here once you begin
            </p>
            <Link
              href="/dashboard/resumes"
              className="mt-4 inline-flex items-center gap-1.5 text-sm font-medium text-foreground hover:text-foreground/70 transition-colors"
            >
              Upload resumes
              <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </motion.div>
        )}

        {loaded && hasResumesButNoAnalyses && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.25 }}
            className="rounded-xl border border-dashed bg-muted/20 px-6 py-12 text-center"
          >
            <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-muted/60">
              <Play className="h-5 w-5 text-muted-foreground/60" />
            </div>
            <p className="text-sm font-medium text-foreground/80">
              Analyze your first resume
            </p>
            <p className="mt-1 text-sm text-muted-foreground">
              You have {s.total_resumes} resume{s.total_resumes !== 1 ? "s" : ""} uploaded. Run an analysis to see insights.
            </p>
            <Link
              href="/dashboard/resumes"
              className="mt-4 inline-flex items-center gap-1.5 text-sm font-medium text-foreground hover:text-foreground/70 transition-colors"
            >
              Go to resumes
              <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </motion.div>
        )}
      </motion.div>
    </DashboardLayout>
  )
}
