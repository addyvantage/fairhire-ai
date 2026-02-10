"use client"

import { useEffect, useMemo, useState } from "react"
import Link from "next/link"
import { useParams, useRouter } from "next/navigation"
import {
  AlertCircle,
  ArrowLeft,
  CheckCircle2,
  CircleDashed,
  ChevronDown,
  ChevronUp,
  Clipboard,
  FileText,
  Lightbulb,
  Link2,
  Sparkles,
  WandSparkles,
} from "lucide-react"
import { motion } from "framer-motion"
import { useAuth } from "@/lib/auth-context"
import { AnalysisResult, getAnalysisByResume, getAnalysisHistoryByResume, getJobProfile, JobProfile } from "@/lib/api"
import { ScoreBreakdown } from "@/components/charts/score-breakdown"
import { DashboardLayout } from "@/components/layout/dashboard-layout"
import { Button } from "@/components/ui/button"
import { EmptyState } from "@/components/ui/empty-state"
import { PageTransition } from "@/components/ui/page-transition"
import { SectionCard } from "@/components/ui/section-card"
import { Skeleton } from "@/components/ui/skeleton"
import { StatusPill } from "@/components/ui/status-pill"
import { useToast } from "@/components/ui/use-toast"
import { transitions } from "@/lib/motion"

function formatDateTime(value: string | null) {
  if (!value) return "—"
  const date = new Date(value)
  if (isNaN(date.getTime())) return "—"
  return date.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  })
}

function AnalysisSkeleton() {
  return (
    <DashboardLayout title="Analysis Results" description="Scoring candidate alignment and fit quality.">
      <div className="mx-auto w-full max-w-6xl space-y-6">
        <Skeleton className="h-10 w-48 rounded-xl" />
        <Skeleton className="h-56 w-full rounded-[var(--radius)]" />
        <div className="grid gap-4 lg:grid-cols-2">
          <Skeleton className="h-60 w-full rounded-[var(--radius)]" />
          <Skeleton className="h-60 w-full rounded-[var(--radius)]" />
        </div>
        <Skeleton className="h-80 w-full rounded-[var(--radius)]" />
      </div>
    </DashboardLayout>
  )
}

export default function AnalysisPage() {
  const params = useParams()
  const resumeId = Number(params.resumeId)
  const router = useRouter()
  const { token, isAuthenticated, isLoading: authLoading } = useAuth()
  const { toast } = useToast()

  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null)
  const [analysisHistory, setAnalysisHistory] = useState<AnalysisResult[]>([])
  const [profileNames, setProfileNames] = useState<Record<number, string>>({})
  const [jobProfile, setJobProfile] = useState<JobProfile | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showRawDetails, setShowRawDetails] = useState(false)

  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.replace("/login")
    }
  }, [authLoading, isAuthenticated, router])

  useEffect(() => {
    if (!token || !resumeId) return

    const authToken = token
    let cancelled = false
    let interval: ReturnType<typeof setInterval> | undefined

    async function load() {
      try {
        const result = await getAnalysisByResume(authToken, resumeId)
        if (cancelled) return
        if (!result) {
          setError("No analysis found for this resume.")
          setLoading(false)
          return
        }

        setAnalysis(result)
        setLoading(false)

        const history = await getAnalysisHistoryByResume(authToken, resumeId).catch(() => [])
        if (!cancelled) {
          setAnalysisHistory(history)
        }

        const profileIds = Array.from(
          new Set(
            history
              .map((entry) => entry.job_profile_id)
              .filter((value): value is number => typeof value === "number")
          )
        )
        if (profileIds.length > 0) {
          const pairs = await Promise.all(
            profileIds.map(async (profileId) => {
              try {
                const profile = await getJobProfile(authToken, profileId)
                return [profileId, profile.title] as const
              } catch {
                return [profileId, `Role ${profileId}`] as const
              }
            })
          )
          if (!cancelled) {
            setProfileNames(Object.fromEntries(pairs))
          }
        }

        if (result.job_profile_id) {
          getJobProfile(authToken, result.job_profile_id)
            .then((profile) => {
              if (!cancelled) setJobProfile(profile)
            })
            .catch(() => undefined)
        }

        if (result.status === "queued" || result.status === "processing") {
          interval = setInterval(async () => {
            try {
              const next = await getAnalysisByResume(authToken, resumeId)
              if (!next || cancelled) return
              setAnalysis(next)
              if (next.status === "completed" || next.status === "failed") {
                clearInterval(interval)
              }
            } catch {
              return
            }
          }, 2500)
        }
      } catch {
        if (!cancelled) {
          setError("Unable to load this analysis.")
          setLoading(false)
        }
      }
    }

    load()
    return () => {
      cancelled = true
      if (interval) clearInterval(interval)
    }
  }, [resumeId, token])

  const jobMatchResult = analysis?.job_match_result ?? null

  const inProgress = analysis?.status === "queued" || analysis?.status === "processing"
  const failed = analysis?.status === "failed"
  const targeted = analysis?.status === "completed" && Boolean(jobMatchResult)
  const profileTitle = jobProfile?.title ?? "Target role"
  const profileSeniority = jobProfile?.seniority_level
    ? ` (${jobProfile.seniority_level.replace("-", " ")})`
    : ""

  const scoreRows = targeted
    ? jobMatchResult?.dimension_scores?.length
      ? jobMatchResult.dimension_scores.map((dimension) => ({
          label: dimension.label,
          score: dimension.score,
          weight: `${dimension.weight.toFixed(0)}%`,
          tone:
            dimension.key === "skills_tools"
              ? ("primary" as const)
              : dimension.key === "responsibility_alignment"
                ? ("success" as const)
                : dimension.key === "domain_familiarity"
                  ? ("warning" as const)
                  : ("neutral" as const),
        }))
      : [
          { label: "Skills Match", score: jobMatchResult!.skill_match_score, weight: "40%", tone: "primary" as const },
          { label: "Experience Match", score: jobMatchResult!.experience_match_score, weight: "25%", tone: "success" as const },
          { label: "Role Alignment", score: jobMatchResult!.role_alignment_score, weight: "15%", tone: "warning" as const },
          { label: "Seniority Fit", score: jobMatchResult!.seniority_fit_score, weight: "10%", tone: "neutral" as const },
          { label: "Resume Quality", score: jobMatchResult!.quality_score, weight: "10%", tone: "primary" as const },
        ]
    : []

  const rejectionRisks = jobMatchResult?.rejection_risks ?? []
  const fastestFixes = jobMatchResult?.fastest_fixes ?? []
  const missingEvidence = jobMatchResult?.missing_evidence ?? []
  const rewriteSuggestions = jobMatchResult?.rewrite_suggestions ?? []
  const atsKeywordMap = jobMatchResult?.ats_keyword_map ?? []
  const comparisonRows = jobMatchResult?.resume_vs_jd_comparison ?? []
  const multiRoleComparisons = analysisHistory
    .filter((entry) => entry.status === "completed" && entry.job_match_result && entry.job_profile_id)
    .slice(0, 4)

  const skillColumns = useMemo(() => {
    if (!jobMatchResult) return null
    return [
      {
        label: "Matched skills",
        tone: "bg-emerald-50 text-emerald-700",
        items: [
          ...jobMatchResult.details.matched_required,
          ...jobMatchResult.details.matched_optional,
        ],
      },
      {
        label: "Missing skills",
        tone: "bg-rose-50 text-rose-700",
        items: jobMatchResult.details.missing_required,
      },
      {
        label: "Additional skills",
        tone: "bg-slate-100 text-slate-700",
        items: jobMatchResult.details.extra_resume_skills,
      },
    ]
  }, [jobMatchResult])

  if (authLoading || !isAuthenticated || loading) return <AnalysisSkeleton />

  if (!analysis || error) {
    return (
      <DashboardLayout title="Analysis Results" description="Scoring candidate alignment and fit quality.">
        <div className="mx-auto w-full max-w-4xl">
          <EmptyState
            icon={<AlertCircle className="h-5 w-5" />}
            title={error ?? "No analysis available"}
            description="Return to resumes and launch a new analysis run."
            action={
              <Button asChild>
                <Link href="/dashboard/resumes">Back to resumes</Link>
              </Button>
            }
          />
        </div>
      </DashboardLayout>
    )
  }

  async function copyShareLink() {
    try {
      await navigator.clipboard.writeText(window.location.href)
      toast({ title: "Link copied", description: "Analysis URL is ready to share." })
    } catch {
      toast({ title: "Copy failed", description: "Unable to copy link.", variant: "destructive" })
    }
  }

  async function copyText(value: string) {
    try {
      await navigator.clipboard.writeText(value)
      toast({ title: "Copied", description: "Suggestion copied to clipboard." })
    } catch {
      toast({ title: "Copy failed", description: "Unable to copy text.", variant: "destructive" })
    }
  }

  return (
    <DashboardLayout
      title="Analysis Results"
      description="Scoring candidate alignment and fit quality."
      actions={
        <>
          <Button size="sm" variant="outline" onClick={copyShareLink}>
            <Link2 className="h-4 w-4" />
            Share
          </Button>
          <Button size="sm" variant="outline" asChild>
            <Link href="/dashboard/resumes">
              <ArrowLeft className="h-4 w-4" />
              Back to resumes
            </Link>
          </Button>
        </>
      }
    >
      <PageTransition className="mx-auto w-full max-w-6xl">
        <section className="surface-elevated overflow-hidden border border-primary/15">
          <div className="grid gap-4 p-6 lg:grid-cols-[1.2fr_1fr] lg:p-8">
            <div className="space-y-4">
              <p className="inline-flex items-center gap-2 rounded-full bg-primary-soft px-3 py-1 text-xs font-semibold uppercase tracking-[0.1em] text-primary">
                <Sparkles className="h-3.5 w-3.5" />
                Candidate fit score
              </p>
              <h2 className="text-balance text-3xl font-semibold tracking-tight text-foreground sm:text-4xl">
                {analysis.match_score ?? analysis.job_match_result?.overall_match_score ?? "—"}% match for{" "}
                <span className="text-primary">
                  {targeted ? `${profileTitle}${profileSeniority}` : "this resume"}
                </span>
              </h2>
              <div className="flex flex-wrap items-center gap-2">
                <StatusPill status={analysis.status} />
                <span className="rounded-full bg-muted px-2.5 py-1 text-xs font-medium text-muted-foreground">
                  Started {formatDateTime(analysis.started_at)}
                </span>
                <span className="rounded-full bg-muted px-2.5 py-1 text-xs font-medium text-muted-foreground">
                  Completed {formatDateTime(analysis.completed_at)}
                </span>
              </div>
            </div>
            <div className="rounded-2xl border border-border/80 bg-background p-5">
              <p className="text-xs font-semibold uppercase tracking-[0.08em] text-muted-foreground">
                Analysis Snapshot
              </p>
              <div className="mt-4 grid grid-cols-2 gap-3">
                <SnapshotStat label="Job profile" value={analysis.job_profile_id ? "Targeted" : "General"} />
                <SnapshotStat
                  label="Experience detected"
                  value={
                    analysis.job_match_result
                      ? `${analysis.job_match_result.details.experience_years_detected} yrs`
                      : `${analysis.extracted_metadata?.experience_years ?? 0} yrs`
                  }
                />
                <SnapshotStat
                  label="Matched required"
                  value={`${analysis.job_match_result?.details.matched_required.length ?? 0}`}
                />
                <SnapshotStat
                  label="Missing required"
                  value={`${analysis.job_match_result?.details.missing_required.length ?? 0}`}
                />
              </div>
            </div>
          </div>
        </section>

        {inProgress && (
          <SectionCard title="Analysis is running" description="This view refreshes automatically in the background.">
            <div className="space-y-3">
              <Skeleton className="h-3 w-full rounded-full" />
              <Skeleton className="h-3 w-11/12 rounded-full" />
              <Skeleton className="h-3 w-3/4 rounded-full" />
            </div>
          </SectionCard>
        )}

        {failed && (
          <SectionCard title="Analysis failed" description={analysis.error_message ?? "An unknown issue interrupted this run."}>
            <div className="flex items-center gap-2 rounded-xl border border-destructive/25 bg-destructive/5 px-4 py-3 text-sm text-destructive">
              <AlertCircle className="h-4 w-4" />
              Try re-running the analysis from the resumes page.
            </div>
          </SectionCard>
        )}

        {targeted && !inProgress && !failed && (
          <>
            <div className="grid gap-4 lg:grid-cols-2">
              <SectionCard title="Score Breakdown" description="Weighted dimensions used to compute fit.">
                <ScoreBreakdown scores={scoreRows} />
              </SectionCard>
              <SectionCard title="Recruiter Verdict" description="How this profile reads to a hiring team.">
                <div className="space-y-3">
                  <p className="text-sm leading-relaxed text-foreground">
                    {jobMatchResult?.recruiter_verdict ?? analysis.job_match_result?.explanation_summary}
                  </p>
                  <div className="rounded-xl border border-border/80 bg-muted/30 p-3">
                    <p className="text-xs font-semibold uppercase tracking-[0.08em] text-muted-foreground">
                      Explanation summary
                    </p>
                    <p className="mt-1 text-sm leading-relaxed text-foreground">
                      {analysis.job_match_result?.explanation_summary}
                    </p>
                  </div>
                </div>
              </SectionCard>
            </div>

            <div className="grid gap-4 lg:grid-cols-2">
              <SectionCard title="Strengths" description="Where the candidate is strongest for this role.">
                <ul className="space-y-2">
                  {analysis.job_match_result?.strengths.length ? (
                    analysis.job_match_result.strengths.map((item) => (
                      <li key={item} className="flex items-start gap-2 text-sm text-foreground">
                        <CheckCircle2 className="mt-0.5 h-4 w-4 text-emerald-600" />
                        {item}
                      </li>
                    ))
                  ) : (
                    <li className="text-sm text-muted-foreground">No strengths captured.</li>
                  )}
                </ul>
              </SectionCard>

              <SectionCard title="Gaps" description="Critical competencies missing or underrepresented.">
                <ul className="space-y-2">
                  {analysis.job_match_result?.gaps.length ? (
                    analysis.job_match_result.gaps.map((item) => (
                      <li key={item} className="flex items-start gap-2 text-sm text-foreground">
                        <AlertCircle className="mt-0.5 h-4 w-4 text-rose-600" />
                        {item}
                      </li>
                    ))
                  ) : (
                    <li className="text-sm text-muted-foreground">No significant gaps detected.</li>
                  )}
                </ul>
              </SectionCard>
            </div>

            <div className="grid gap-4 lg:grid-cols-2">
              <SectionCard title="Why You Might Get Rejected" description="Likely recruiter blockers from this run.">
                <ul className="space-y-2">
                  {rejectionRisks.length > 0 ? (
                    rejectionRisks.map((item) => (
                      <li key={item} className="flex items-start gap-2 text-sm text-foreground">
                        <AlertCircle className="mt-0.5 h-4 w-4 text-rose-600" />
                        {item}
                      </li>
                    ))
                  ) : (
                    <li className="text-sm text-muted-foreground">No major rejection triggers identified.</li>
                  )}
                </ul>
              </SectionCard>

              <SectionCard title="Fastest Fixes" description="Highest-impact changes to improve match quickly.">
                <ul className="space-y-2">
                  {fastestFixes.length > 0 ? (
                    fastestFixes.map((item) => (
                      <li key={item} className="flex items-start gap-2 text-sm text-foreground">
                        <Lightbulb className="mt-0.5 h-4 w-4 text-amber-600" />
                        {item}
                      </li>
                    ))
                  ) : (
                    <li className="text-sm text-muted-foreground">No quick fixes available for this run.</li>
                  )}
                </ul>
              </SectionCard>
            </div>

            {skillColumns && (
              <SectionCard title="Skills Matrix" description="Matched, missing, and additional capabilities at a glance.">
                <div className="grid gap-4 lg:grid-cols-3">
                  {skillColumns.map((column) => (
                    <div key={column.label} className="rounded-xl border border-border/70 bg-muted/30 p-4">
                      <p className="mb-3 text-xs font-semibold uppercase tracking-[0.08em] text-muted-foreground">
                        {column.label}
                      </p>
                      <div className="flex flex-wrap gap-1.5">
                        {column.items.length > 0 ? (
                          column.items.map((item) => (
                            <span key={item} className={`rounded-full px-2.5 py-1 text-xs font-medium ${column.tone}`}>
                              {item}
                            </span>
                          ))
                        ) : (
                          <span className="text-xs text-muted-foreground">None</span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </SectionCard>
            )}

            <div className="grid gap-4 lg:grid-cols-2">
              <SectionCard title="Missing Evidence" description="Missing proof, not just missing keywords.">
                <ul className="space-y-2">
                  {missingEvidence.length > 0 ? (
                    missingEvidence.map((item) => (
                      <li key={item} className="flex items-start gap-2 text-sm text-foreground">
                        <CircleDashed className="mt-0.5 h-4 w-4 text-slate-500" />
                        {item}
                      </li>
                    ))
                  ) : (
                    <li className="text-sm text-muted-foreground">
                      Evidence quality looks healthy for matched requirements.
                    </li>
                  )}
                </ul>
              </SectionCard>

              <SectionCard title="ATS Keyword Placement" description="Where critical terms are present or missing.">
                <div className="flex flex-wrap gap-2">
                  {atsKeywordMap.length > 0 ? (
                    atsKeywordMap.map((entry) => (
                      <span
                        key={`${entry.keyword}-${entry.location_hint}`}
                        title={entry.evidence?.[0] ?? "No direct evidence snippet"}
                        className={
                          entry.status === "matched"
                            ? "rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-700"
                            : "rounded-full bg-rose-50 px-2.5 py-1 text-xs font-medium text-rose-700"
                        }
                      >
                        {entry.keyword} · {entry.location_hint}
                      </span>
                    ))
                  ) : (
                    <span className="text-sm text-muted-foreground">No ATS keyword map available.</span>
                  )}
                </div>
              </SectionCard>
            </div>

            <SectionCard title="Bullet Rewrite Suggestions" description="Copy-ready rewrites grounded in analysis evidence.">
              <div className="space-y-3">
                {rewriteSuggestions.length > 0 ? (
                  rewriteSuggestions.map((item, index) => (
                    <div key={`${item.requirement}-${index}`} className="rounded-xl border border-border/70 bg-muted/20 p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="text-sm font-semibold text-foreground">{item.requirement}</p>
                          <p className="mt-1 text-xs text-muted-foreground">{item.issue}</p>
                        </div>
                        <Button size="sm" variant="outline" onClick={() => copyText(item.example_bullet)}>
                          <WandSparkles className="h-4 w-4" />
                          Copy
                        </Button>
                      </div>
                      <p className="mt-3 text-sm text-foreground">{item.recommendation}</p>
                      <p className="mt-2 rounded-lg bg-background px-3 py-2 text-sm text-foreground/85">
                        {item.example_bullet}
                      </p>
                    </div>
                  ))
                ) : (
                  <p className="text-sm text-muted-foreground">No rewrite suggestions generated for this run.</p>
                )}
              </div>
            </SectionCard>

            <SectionCard title="Resume vs JD Comparison" description="Coverage of responsibility clusters.">
              <div className="space-y-2">
                {comparisonRows.length > 0 ? (
                  comparisonRows.map((row) => (
                    <div key={row.cluster} className="rounded-xl border border-border/70 bg-muted/20 px-4 py-3">
                      <div className="flex items-center justify-between gap-3">
                        <p className="text-sm font-medium text-foreground">{row.cluster}</p>
                        <p className="text-sm font-semibold tabular-nums text-foreground">{row.coverage_score}%</p>
                      </div>
                      <p className="mt-1 text-xs text-muted-foreground">
                        {row.matched_items}/{row.jd_items} responsibility signals matched
                      </p>
                    </div>
                  ))
                ) : (
                  <p className="text-sm text-muted-foreground">No responsibility comparison available.</p>
                )}
              </div>
            </SectionCard>

            <SectionCard title="Multi-Role Comparison" description="How this resume performs across role targets.">
              {multiRoleComparisons.length > 0 ? (
                <div className="grid gap-3 md:grid-cols-2">
                  {multiRoleComparisons.map((entry) => (
                    <div key={entry.id} className="rounded-xl border border-border/70 bg-muted/20 px-4 py-3">
                      <div className="flex items-center justify-between gap-3">
                        <p className="text-sm font-medium text-foreground">
                          {entry.job_profile_id ? profileNames[entry.job_profile_id] ?? `Role ${entry.job_profile_id}` : "General"}
                        </p>
                        <p className="text-sm font-semibold tabular-nums text-foreground">
                          {entry.match_score ?? entry.job_match_result?.overall_match_score ?? "—"}%
                        </p>
                      </div>
                      <p className="mt-1 text-xs text-muted-foreground">
                        {entry.job_match_result?.recruiter_verdict ?? entry.job_match_result?.explanation_summary ?? "No summary available."}
                      </p>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">
                  Run this resume against additional job profiles to compare role fit side-by-side.
                </p>
              )}
            </SectionCard>
          </>
        )}

        {!targeted && analysis.status === "completed" && analysis.extracted_metadata && (
          <SectionCard title="Resume Metadata" description="Detected sections and resume quality indicators.">
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <SnapshotStat label="Skills found" value={`${analysis.extracted_metadata.skill_count}`} />
              <SnapshotStat label="Sections found" value={`${analysis.extracted_metadata.section_count}`} />
              <SnapshotStat label="Word count" value={`${analysis.extracted_metadata.word_count}`} />
              <SnapshotStat
                label="Experience"
                value={`${analysis.extracted_metadata.experience_years || 0} yrs`}
              />
            </div>
            <div className="mt-4 flex flex-wrap gap-1.5">
              {analysis.extracted_metadata.skills.map((skill) => (
                <span key={skill} className="rounded-full bg-muted px-2.5 py-1 text-xs text-muted-foreground">
                  {skill}
                </span>
              ))}
            </div>
          </SectionCard>
        )}

        <section className="surface-card overflow-hidden">
          <button
            type="button"
            onClick={() => setShowRawDetails((value) => !value)}
            className="flex w-full items-center justify-between px-5 py-4 text-left"
          >
            <div className="flex items-center gap-2">
              <Clipboard className="h-4 w-4 text-muted-foreground" />
              <p className="text-sm font-semibold text-foreground">Raw analysis data</p>
            </div>
            {showRawDetails ? (
              <ChevronUp className="h-4 w-4 text-muted-foreground" />
            ) : (
              <ChevronDown className="h-4 w-4 text-muted-foreground" />
            )}
          </button>
          <AnimateRaw open={showRawDetails}>
            <div className="border-t border-border/80 px-5 py-4">
              <pre className="max-h-96 overflow-auto rounded-lg bg-muted/40 p-4 text-xs text-foreground/85">
                {JSON.stringify(analysis, null, 2)}
              </pre>
            </div>
          </AnimateRaw>
        </section>

        <div className="rounded-xl border border-dashed border-border/80 bg-muted/20 px-4 py-3 text-sm text-muted-foreground">
          <p className="inline-flex items-center gap-2">
            <FileText className="h-4 w-4" />
            This report is shareable. Use “Share” to copy a direct link.
          </p>
        </div>
      </PageTransition>
    </DashboardLayout>
  )
}

function SnapshotStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-border/70 bg-muted/30 px-3 py-2.5">
      <p className="text-xs uppercase tracking-[0.08em] text-muted-foreground">{label}</p>
      <p className="mt-1 text-lg font-semibold tabular-nums text-foreground">{value}</p>
    </div>
  )
}

function AnimateRaw({ open, children }: { open: boolean; children: React.ReactNode }) {
  return (
    <motion.div
      initial={false}
      animate={open ? { height: "auto", opacity: 1 } : { height: 0, opacity: 0 }}
      transition={transitions.fast}
      className="overflow-hidden"
    >
      {children}
    </motion.div>
  )
}
