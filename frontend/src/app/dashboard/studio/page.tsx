"use client"

import Link from "next/link"
import { useEffect, useMemo, useState } from "react"
import { useRouter } from "next/navigation"
import { ArrowRight, Clock3, FileText, Plus, Sparkles, Tags } from "lucide-react"
import { useAuth } from "@/lib/auth-context"
import { StudioProject, listStudioProjects } from "@/lib/api"
import { DashboardLayout } from "@/components/layout/dashboard-layout"
import { Button } from "@/components/ui/button"
import { EmptyState } from "@/components/ui/empty-state"
import { PageTransition } from "@/components/ui/page-transition"
import { Skeleton } from "@/components/ui/skeleton"

function StudioSkeleton() {
  return (
    <DashboardLayout title="Resume Studio" description="Build, tailor, and export investor-grade resumes.">
      <div className="mx-auto w-full max-w-6xl space-y-6">
        <Skeleton className="h-12 w-64 rounded-xl" />
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }).map((_, index) => (
            <Skeleton key={index} className="h-44 w-full rounded-[var(--radius)]" />
          ))}
        </div>
      </div>
    </DashboardLayout>
  )
}

function formatDate(value: string | null) {
  if (!value) return "—"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return "—"
  return date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  })
}

export default function ResumeStudioPage() {
  const { token, isAuthenticated, isLoading } = useAuth()
  const router = useRouter()
  const [projects, setProjects] = useState<StudioProject[]>([])
  const [loaded, setLoaded] = useState(false)

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.replace("/login")
    }
  }, [isAuthenticated, isLoading, router])

  useEffect(() => {
    if (!token) return
    listStudioProjects(token)
      .then((value) => setProjects(value))
      .catch(() => setProjects([]))
      .finally(() => setLoaded(true))
  }, [token])

  const sortedProjects = useMemo(
    () =>
      [...projects].sort((a, b) => {
        const aTime = new Date(a.updated_at).getTime()
        const bTime = new Date(b.updated_at).getTime()
        return bTime - aTime
      }),
    [projects]
  )

  if (isLoading || !isAuthenticated || !loaded) return <StudioSkeleton />

  return (
    <DashboardLayout
      title="Resume Studio"
      description="Create polished resumes, tailor by JD, and ship ATS-ready exports."
      actions={
        <Button asChild size="sm">
          <Link href="/dashboard/studio/new">
            <Plus className="h-4 w-4" />
            New Resume Studio
          </Link>
        </Button>
      }
    >
      <PageTransition className="mx-auto w-full max-w-6xl">
        {sortedProjects.length === 0 ? (
          <EmptyState
            icon={<Sparkles className="h-5 w-5" />}
            title="No studio projects yet"
            description="Start a new project to build from scratch or improve an existing resume."
            action={
              <Button asChild>
                <Link href="/dashboard/studio/new">Create project</Link>
              </Button>
            }
          />
        ) : (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {sortedProjects.map((project) => (
              <Link
                key={project.id}
                href={`/dashboard/studio/${project.id}`}
                className="surface-card group space-y-4 p-5 transition hover:-translate-y-0.5 hover:shadow-[var(--shadow-md)]"
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-lg font-semibold tracking-tight text-foreground">{project.title}</p>
                    <p className="mt-1 text-sm capitalize text-muted-foreground">
                      {project.source_type.replaceAll("_", " ")}
                    </p>
                  </div>
                  <ArrowRight className="h-4 w-4 text-muted-foreground transition group-hover:translate-x-0.5 group-hover:text-foreground" />
                </div>

                <div className="space-y-2 text-sm text-muted-foreground">
                  <p className="inline-flex items-center gap-2">
                    <Clock3 className="h-3.5 w-3.5" />
                    Updated {formatDate(project.updated_at)}
                  </p>
                  <p className="inline-flex items-center gap-2">
                    <FileText className="h-3.5 w-3.5" />
                    Latest {project.latest_version_kind ?? "base"} version
                  </p>
                  {project.tailored_tags.length > 0 && (
                    <p className="inline-flex items-center gap-2">
                      <Tags className="h-3.5 w-3.5" />
                      {project.tailored_tags.slice(0, 2).join(" • ")}
                    </p>
                  )}
                </div>
              </Link>
            ))}
          </div>
        )}
      </PageTransition>
    </DashboardLayout>
  )
}
