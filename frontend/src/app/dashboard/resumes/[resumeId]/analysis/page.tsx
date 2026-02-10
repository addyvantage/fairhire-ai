"use client"

import { useEffect, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import Link from "next/link"
import {
  ArrowLeft,
  CheckCircle2,
  Clock,
  AlertCircle,
  Loader2,
  Briefcase,
  GraduationCap,
  Code2,
  FolderOpen,
  Award,
  User,
  Mail,
  Phone,
  Linkedin,
  ChevronDown,
  ChevronUp,
  FileText,
} from "lucide-react"
import { motion } from "framer-motion"
import { useAuth } from "@/lib/auth-context"
import { getAnalysisByResume, type AnalysisResult } from "@/lib/api"
import { DashboardLayout } from "@/components/layout/dashboard-layout"
import { Sidebar } from "@/components/layout/sidebar"
import { Skeleton } from "@/components/ui/skeleton"
import { Button } from "@/components/ui/button"

function AnalysisSkeleton() {
  return (
    <DashboardLayout sidebar={<Sidebar />}>
      <div className="mx-auto max-w-3xl space-y-6">
        <Skeleton className="h-5 w-32" />
        <Skeleton className="h-8 w-48" />
        <div className="grid gap-4 sm:grid-cols-2">
          <Skeleton className="h-32 rounded-xl" />
          <Skeleton className="h-32 rounded-xl" />
        </div>
        <Skeleton className="h-48 rounded-xl" />
        <Skeleton className="h-32 rounded-xl" />
      </div>
    </DashboardLayout>
  )
}

const sectionIcons: Record<string, typeof Briefcase> = {
  experience: Briefcase,
  education: GraduationCap,
  skills: Code2,
  projects: FolderOpen,
  certifications: Award,
  summary: User,
}

function formatTimestamp(ts: string | null): string {
  if (!ts) return "—"
  const date = new Date(ts)
  if (isNaN(date.getTime())) return "—"
  return date.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  })
}

export default function AnalysisPage() {
  const params = useParams()
  const resumeId = Number(params.resumeId)
  const { token, isAuthenticated, isLoading: authLoading } = useAuth()
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showRawMeta, setShowRawMeta] = useState(false)
  const router = useRouter()

  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.replace("/login")
    }
  }, [authLoading, isAuthenticated, router])

  useEffect(() => {
    if (!token || !resumeId) return

    let cancelled = false
    let interval: ReturnType<typeof setInterval> | undefined

    async function fetchAnalysis() {
      try {
        const result = await getAnalysisByResume(token!, resumeId)
        if (cancelled) return

        if (!result) {
          setError("No analysis found for this resume")
          setLoading(false)
          return
        }

        setAnalysis(result)
        setLoading(false)

        if (result.status === "queued" || result.status === "processing") {
          interval = setInterval(async () => {
            try {
              const updated = await getAnalysisByResume(token!, resumeId)
              if (cancelled || !updated) return
              setAnalysis(updated)
              if (updated.status === "completed" || updated.status === "failed") {
                clearInterval(interval)
              }
            } catch {
              // retry silently
            }
          }, 3000)
        }
      } catch {
        if (!cancelled) {
          setError("Failed to load analysis")
          setLoading(false)
        }
      }
    }

    fetchAnalysis()

    return () => {
      cancelled = true
      if (interval) clearInterval(interval)
    }
  }, [token, resumeId])

  if (authLoading || !isAuthenticated) return <AnalysisSkeleton />
  if (loading) return <AnalysisSkeleton />

  if (error || !analysis) {
    return (
      <DashboardLayout sidebar={<Sidebar />}>
        <div className="mx-auto max-w-3xl">
          <Link
            href="/dashboard/resumes"
            className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors mb-6"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Back to resumes
          </Link>
          <div className="rounded-xl border border-dashed bg-muted/20 py-16 text-center">
            <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-muted/60">
              <AlertCircle className="h-5 w-5 text-muted-foreground/60" />
            </div>
            <p className="text-sm font-medium text-foreground/80">
              {error || "No analysis found"}
            </p>
            <p className="mt-1 text-sm text-muted-foreground">
              Go back to resumes and run an analysis first
            </p>
            <Link href="/dashboard/resumes">
              <Button variant="outline" size="sm" className="mt-4">
                Go to Resumes
              </Button>
            </Link>
          </div>
        </div>
      </DashboardLayout>
    )
  }

  const meta = analysis.extracted_metadata
  const isInFlight = analysis.status === "queued" || analysis.status === "processing"
  const isFailed = analysis.status === "failed"

  return (
    <DashboardLayout sidebar={<Sidebar />}>
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
        className="mx-auto max-w-3xl space-y-6"
      >
        <Link
          href="/dashboard/resumes"
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Back to resumes
        </Link>

        <div>
          <h1 className="text-xl font-semibold tracking-tight text-foreground">
            Resume Analysis
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Detailed analysis results
          </p>
        </div>

        {/* Status Timeline */}
        <div className="rounded-xl border bg-background p-5">
          <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground mb-3">
            Status
          </p>
          <div className="flex items-center gap-3">
            <StatusStep
              label="Queued"
              active={analysis.status === "queued"}
              completed={analysis.status !== "queued"}
            />
            <StatusConnector
              completed={analysis.status === "processing" || analysis.status === "completed"}
            />
            <StatusStep
              label="Processing"
              active={analysis.status === "processing"}
              completed={analysis.status === "completed"}
            />
            <StatusConnector completed={analysis.status === "completed"} />
            <StatusStep
              label={isFailed ? "Failed" : "Completed"}
              active={analysis.status === "completed" || isFailed}
              completed={analysis.status === "completed"}
              failed={isFailed}
            />
          </div>
          {analysis.started_at && (
            <p className="mt-3 text-xs text-muted-foreground">
              Started: {formatTimestamp(analysis.started_at)}
            </p>
          )}
          {analysis.completed_at && (
            <p className="text-xs text-muted-foreground">
              Completed: {formatTimestamp(analysis.completed_at)}
            </p>
          )}
        </div>

        {/* In-flight state */}
        {isInFlight && (
          <div className="rounded-xl border bg-background p-8 text-center">
            <Loader2 className="h-8 w-8 animate-spin mx-auto text-muted-foreground mb-3" />
            <p className="text-sm font-medium text-foreground">
              Analysis in progress
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              This page will update automatically when complete
            </p>
          </div>
        )}

        {/* Failed state */}
        {isFailed && (
          <div className="rounded-xl border border-destructive/30 bg-destructive/5 p-5">
            <div className="flex items-start gap-3">
              <AlertCircle className="h-5 w-5 text-destructive shrink-0 mt-0.5" />
              <div>
                <p className="text-sm font-medium text-foreground">Analysis failed</p>
                <p className="text-xs text-muted-foreground mt-1">
                  {analysis.error_message || "An unknown error occurred"}
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Completed results */}
        {analysis.status === "completed" && meta && (
          <>
            {/* Score Hero */}
            <div className="rounded-xl border bg-background p-6 text-center">
              <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground mb-2">
                Match Score
              </p>
              <div className="text-5xl font-bold tracking-tight text-foreground tabular-nums">
                {analysis.match_score}
                <span className="text-2xl text-muted-foreground">%</span>
              </div>
            </div>

            {/* Stats Grid */}
            <div className="grid gap-4 sm:grid-cols-3">
              <div className="rounded-xl border bg-background p-4">
                <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                  Skills Found
                </p>
                <p className="mt-1 text-2xl font-semibold tabular-nums text-foreground">
                  {meta.skill_count}
                </p>
              </div>
              <div className="rounded-xl border bg-background p-4">
                <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                  Experience
                </p>
                <p className="mt-1 text-2xl font-semibold tabular-nums text-foreground">
                  {meta.experience_years > 0
                    ? `${meta.experience_years} yr${meta.experience_years !== 1 ? "s" : ""}`
                    : "—"}
                </p>
              </div>
              <div className="rounded-xl border bg-background p-4">
                <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                  Word Count
                </p>
                <p className="mt-1 text-2xl font-semibold tabular-nums text-foreground">
                  {meta.word_count.toLocaleString()}
                </p>
              </div>
            </div>

            {/* Skills */}
            <div className="rounded-xl border bg-background p-5">
              <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground mb-3">
                Skills Extracted
              </p>
              {meta.skills.length > 0 ? (
                <div className="flex flex-wrap gap-2">
                  {meta.skills.map((skill) => (
                    <span
                      key={skill}
                      className="inline-flex items-center rounded-md bg-muted/60 px-2.5 py-1 text-xs font-medium text-foreground"
                    >
                      {skill}
                    </span>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">No skills detected</p>
              )}
            </div>

            {/* Sections Detected */}
            <div className="rounded-xl border bg-background p-5">
              <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground mb-3">
                Sections Detected
              </p>
              {meta.sections_detected.length > 0 ? (
                <div className="grid gap-2 sm:grid-cols-2">
                  {meta.sections_detected.map((section) => {
                    const Icon = sectionIcons[section] || FileText
                    return (
                      <div
                        key={section}
                        className="flex items-center gap-2.5 rounded-lg border bg-muted/20 px-3 py-2"
                      >
                        <Icon className="h-4 w-4 text-muted-foreground" />
                        <span className="text-sm font-medium capitalize text-foreground">
                          {section}
                        </span>
                      </div>
                    )
                  })}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">
                  No standard sections detected
                </p>
              )}
            </div>

            {/* Contact Info */}
            <div className="rounded-xl border bg-background p-5">
              <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground mb-3">
                Contact Information
              </p>
              <div className="flex flex-wrap gap-3">
                <ContactBadge
                  icon={Mail}
                  label="Email"
                  present={meta.contact_info.has_email}
                />
                <ContactBadge
                  icon={Phone}
                  label="Phone"
                  present={meta.contact_info.has_phone}
                />
                <ContactBadge
                  icon={Linkedin}
                  label="LinkedIn"
                  present={meta.contact_info.has_linkedin}
                />
              </div>
            </div>

            {/* Raw Metadata (collapsible) */}
            <div className="rounded-xl border bg-background">
              <button
                type="button"
                onClick={() => setShowRawMeta(!showRawMeta)}
                className="flex w-full items-center justify-between p-5 text-left"
              >
                <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                  Raw Metadata
                </p>
                {showRawMeta ? (
                  <ChevronUp className="h-4 w-4 text-muted-foreground" />
                ) : (
                  <ChevronDown className="h-4 w-4 text-muted-foreground" />
                )}
              </button>
              {showRawMeta && (
                <div className="border-t px-5 pb-5">
                  <pre className="mt-3 overflow-x-auto rounded-lg bg-muted/30 p-4 text-xs text-foreground/80">
                    {JSON.stringify(meta, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          </>
        )}
      </motion.div>
    </DashboardLayout>
  )
}

function StatusStep({
  label,
  active,
  completed,
  failed = false,
}: {
  label: string
  active: boolean
  completed: boolean
  failed?: boolean
}) {
  return (
    <div className="flex items-center gap-2">
      {failed ? (
        <AlertCircle className="h-4 w-4 text-destructive" />
      ) : completed ? (
        <CheckCircle2 className="h-4 w-4 text-green-600" />
      ) : active ? (
        <Loader2 className="h-4 w-4 animate-spin text-foreground" />
      ) : (
        <Clock className="h-4 w-4 text-muted-foreground/40" />
      )}
      <span
        className={`text-xs font-medium ${
          failed
            ? "text-destructive"
            : completed
              ? "text-green-600"
              : active
                ? "text-foreground"
                : "text-muted-foreground/40"
        }`}
      >
        {label}
      </span>
    </div>
  )
}

function StatusConnector({ completed }: { completed: boolean }) {
  return (
    <div
      className={`h-px flex-1 ${completed ? "bg-green-600/40" : "bg-border"}`}
    />
  )
}

function ContactBadge({
  icon: Icon,
  label,
  present,
}: {
  icon: typeof Mail
  label: string
  present: boolean
}) {
  return (
    <div
      className={`inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium ${
        present
          ? "bg-green-50 text-green-700 dark:bg-green-950/30 dark:text-green-400"
          : "bg-muted/40 text-muted-foreground"
      }`}
    >
      <Icon className="h-3.5 w-3.5" />
      {label}
      {present ? (
        <CheckCircle2 className="h-3 w-3" />
      ) : (
        <span className="text-[10px] opacity-60">missing</span>
      )}
    </div>
  )
}
