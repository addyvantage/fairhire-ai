"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import { useRouter } from "next/navigation"
import { ColumnDef } from "@tanstack/react-table"
import { Briefcase, Plus, Trash2, Loader2 } from "lucide-react"
import { motion } from "framer-motion"
import { useAuth } from "@/lib/auth-context"
import {
  listJobProfiles,
  createJobProfile,
  deleteJobProfile,
  type JobProfile,
} from "@/lib/api"
import { DashboardLayout } from "@/components/layout/dashboard-layout"
import { Sidebar } from "@/components/layout/sidebar"
import { VirtualizedTable } from "@/components/ui/virtualized-table"
import { Skeleton } from "@/components/ui/skeleton"
import { Button } from "@/components/ui/button"
import { useToast } from "@/components/ui/use-toast"

function JobsSkeleton() {
  return (
    <DashboardLayout sidebar={<Sidebar />}>
      <div className="mx-auto max-w-5xl space-y-8">
        <div className="space-y-2">
          <Skeleton className="h-7 w-32" />
          <Skeleton className="h-4 w-64" />
        </div>
        <Skeleton className="h-48 w-full rounded-xl" />
        <div className="space-y-0 rounded-xl border overflow-hidden">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="border-b last:border-0 px-4 py-3 flex gap-16">
              <Skeleton className="h-4 w-48" />
              <Skeleton className="h-4 w-24" />
              <Skeleton className="h-4 w-20" />
            </div>
          ))}
        </div>
      </div>
    </DashboardLayout>
  )
}

type CreateMode = "paste" | "manual" | null

export default function JobProfilesPage() {
  const { token, isAuthenticated, isLoading } = useAuth()
  const [profiles, setProfiles] = useState<JobProfile[]>([])
  const [loaded, setLoaded] = useState(false)
  const [createMode, setCreateMode] = useState<CreateMode>(null)
  const [creating, setCreating] = useState(false)
  const router = useRouter()
  const { toast } = useToast()

  // Form state for "Paste JD"
  const [pasteTitle, setPasteTitle] = useState("")
  const [pasteText, setPasteText] = useState("")

  // Form state for "Build Manually"
  const [manualTitle, setManualTitle] = useState("")
  const [manualSeniority, setManualSeniority] = useState("")
  const [manualRequiredSkills, setManualRequiredSkills] = useState("")
  const [manualOptionalSkills, setManualOptionalSkills] = useState("")
  const [manualExpMin, setManualExpMin] = useState("")
  const [manualExpMax, setManualExpMax] = useState("")

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.replace("/login")
    }
  }, [isLoading, isAuthenticated, router])

  const fetchProfiles = useCallback(async () => {
    if (!token) return
    try {
      const data = await listJobProfiles(token)
      setProfiles(data)
      setLoaded(true)
    } catch {
      setProfiles([])
      setLoaded(true)
    }
  }, [token])

  useEffect(() => {
    fetchProfiles()
  }, [fetchProfiles])

  async function handleCreatePaste() {
    if (!token || !pasteTitle.trim()) return
    setCreating(true)
    try {
      await createJobProfile(token, {
        title: pasteTitle.trim(),
        raw_description: pasteText.trim() || undefined,
      })
      toast({ title: "Job profile created", description: pasteTitle.trim() })
      setPasteTitle("")
      setPasteText("")
      setCreateMode(null)
      fetchProfiles()
    } catch (err) {
      toast({
        title: "Failed to create profile",
        description: (err as Error).message,
        variant: "destructive",
      })
    } finally {
      setCreating(false)
    }
  }

  async function handleCreateManual() {
    if (!token || !manualTitle.trim()) return
    setCreating(true)
    try {
      const reqSkills = manualRequiredSkills
        .split(",")
        .map((s) => s.trim().toLowerCase())
        .filter(Boolean)
      const optSkills = manualOptionalSkills
        .split(",")
        .map((s) => s.trim().toLowerCase())
        .filter(Boolean)

      await createJobProfile(token, {
        title: manualTitle.trim(),
        seniority_level: manualSeniority || undefined,
        required_skills: reqSkills.length > 0 ? reqSkills : undefined,
        optional_skills: optSkills.length > 0 ? optSkills : undefined,
        years_experience_min: manualExpMin ? parseInt(manualExpMin) : undefined,
        years_experience_max: manualExpMax ? parseInt(manualExpMax) : undefined,
      })
      toast({ title: "Job profile created", description: manualTitle.trim() })
      setManualTitle("")
      setManualSeniority("")
      setManualRequiredSkills("")
      setManualOptionalSkills("")
      setManualExpMin("")
      setManualExpMax("")
      setCreateMode(null)
      fetchProfiles()
    } catch (err) {
      toast({
        title: "Failed to create profile",
        description: (err as Error).message,
        variant: "destructive",
      })
    } finally {
      setCreating(false)
    }
  }

  async function handleDelete(profileId: number) {
    if (!token) return
    try {
      await deleteJobProfile(token, profileId)
      toast({ title: "Profile deleted" })
      fetchProfiles()
    } catch (err) {
      toast({
        title: "Delete failed",
        description: (err as Error).message,
        variant: "destructive",
      })
    }
  }

  const columns: ColumnDef<JobProfile, unknown>[] = useMemo(
    () => [
      {
        accessorKey: "title",
        header: "Title",
        cell: ({ row }) => (
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-muted/60">
              <Briefcase className="h-3.5 w-3.5 text-muted-foreground" />
            </div>
            <div className="min-w-0">
              <span className="font-medium text-foreground truncate block">
                {row.original.title}
              </span>
              {row.original.is_template && (
                <span className="text-[10px] uppercase tracking-wider text-muted-foreground/70">
                  Template
                </span>
              )}
            </div>
          </div>
        ),
      },
      {
        accessorKey: "seniority_level",
        header: "Seniority",
        cell: ({ row }) => {
          const level = row.original.seniority_level
          if (!level) return <span className="text-muted-foreground text-xs">—</span>
          return (
            <span className="inline-flex items-center rounded-full bg-muted/60 px-2 py-0.5 text-xs font-medium capitalize text-foreground/80">
              {level}
            </span>
          )
        },
      },
      {
        id: "skills",
        header: "Skills",
        cell: ({ row }) => {
          const required = row.original.required_skills?.length ?? 0
          const optional = row.original.optional_skills?.length ?? 0
          return (
            <span className="text-muted-foreground text-xs tabular-nums">
              {required} req · {optional} opt
            </span>
          )
        },
      },
      {
        id: "experience",
        header: "Experience",
        cell: ({ row }) => {
          const min = row.original.years_experience_min
          const max = row.original.years_experience_max
          if (min == null && max == null) {
            return <span className="text-muted-foreground text-xs">—</span>
          }
          return (
            <span className="text-muted-foreground text-xs tabular-nums">
              {min ?? 0}–{max ?? "?"} yrs
            </span>
          )
        },
      },
      {
        id: "actions",
        header: "",
        cell: ({ row }) => {
          if (row.original.is_template) return null
          return (
            <div className="flex justify-end">
              <Button
                size="sm"
                variant="ghost"
                className="h-7 w-7 p-0 text-muted-foreground hover:text-destructive"
                onClick={(e) => {
                  e.stopPropagation()
                  handleDelete(row.original.id)
                }}
              >
                <Trash2 className="h-3.5 w-3.5" />
              </Button>
            </div>
          )
        },
      },
    ],
    // eslint-disable-next-line react-hooks/exhaustive-deps
    []
  )

  if (isLoading || !isAuthenticated) {
    return <JobsSkeleton />
  }

  return (
    <DashboardLayout sidebar={<Sidebar />}>
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
        className="mx-auto max-w-5xl space-y-8"
      >
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-xl font-semibold tracking-tight text-foreground">
              Job Profiles
            </h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Define target roles to score resumes against
            </p>
          </div>
          {!createMode && (
            <div className="flex gap-2">
              <Button
                size="sm"
                variant="outline"
                className="gap-1.5 text-xs"
                onClick={() => setCreateMode("paste")}
              >
                <Plus className="h-3 w-3" />
                Paste JD
              </Button>
              <Button
                size="sm"
                variant="default"
                className="gap-1.5 text-xs"
                onClick={() => setCreateMode("manual")}
              >
                <Plus className="h-3 w-3" />
                Build Manually
              </Button>
            </div>
          )}
        </div>

        {/* Create Form: Paste JD */}
        {createMode === "paste" && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            className="rounded-xl border bg-card p-5 space-y-4"
          >
            <h2 className="text-sm font-semibold text-foreground">
              Paste a Job Description
            </h2>
            <p className="text-xs text-muted-foreground">
              We&apos;ll auto-extract skills, seniority, and experience requirements.
            </p>
            <input
              type="text"
              placeholder="Job title (e.g. Senior Frontend Engineer)"
              value={pasteTitle}
              onChange={(e) => setPasteTitle(e.target.value)}
              className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-foreground/10"
            />
            <textarea
              placeholder="Paste the full job description here..."
              value={pasteText}
              onChange={(e) => setPasteText(e.target.value)}
              rows={8}
              className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-foreground/10 resize-none"
            />
            <div className="flex gap-2 justify-end">
              <Button
                size="sm"
                variant="ghost"
                onClick={() => setCreateMode(null)}
                disabled={creating}
              >
                Cancel
              </Button>
              <Button
                size="sm"
                onClick={handleCreatePaste}
                disabled={creating || !pasteTitle.trim()}
                className="gap-1.5"
              >
                {creating && <Loader2 className="h-3 w-3 animate-spin" />}
                Create Profile
              </Button>
            </div>
          </motion.div>
        )}

        {/* Create Form: Build Manually */}
        {createMode === "manual" && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            className="rounded-xl border bg-card p-5 space-y-4"
          >
            <h2 className="text-sm font-semibold text-foreground">
              Build Job Profile Manually
            </h2>
            <div className="grid grid-cols-2 gap-4">
              <div className="col-span-2">
                <label className="text-xs font-medium text-muted-foreground mb-1 block">
                  Job Title
                </label>
                <input
                  type="text"
                  placeholder="e.g. Backend Engineer"
                  value={manualTitle}
                  onChange={(e) => setManualTitle(e.target.value)}
                  className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-foreground/10"
                />
              </div>
              <div>
                <label className="text-xs font-medium text-muted-foreground mb-1 block">
                  Seniority Level
                </label>
                <select
                  value={manualSeniority}
                  onChange={(e) => setManualSeniority(e.target.value)}
                  className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-foreground/10"
                >
                  <option value="">Select...</option>
                  <option value="intern">Intern</option>
                  <option value="junior">Junior</option>
                  <option value="mid">Mid-level</option>
                  <option value="senior">Senior</option>
                  <option value="lead">Lead</option>
                  <option value="principal">Principal</option>
                  <option value="staff">Staff</option>
                </select>
              </div>
              <div>
                <label className="text-xs font-medium text-muted-foreground mb-1 block">
                  Experience (years)
                </label>
                <div className="flex items-center gap-2">
                  <input
                    type="number"
                    placeholder="Min"
                    value={manualExpMin}
                    onChange={(e) => setManualExpMin(e.target.value)}
                    className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-foreground/10"
                  />
                  <span className="text-muted-foreground text-xs">–</span>
                  <input
                    type="number"
                    placeholder="Max"
                    value={manualExpMax}
                    onChange={(e) => setManualExpMax(e.target.value)}
                    className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-foreground/10"
                  />
                </div>
              </div>
              <div className="col-span-2">
                <label className="text-xs font-medium text-muted-foreground mb-1 block">
                  Required Skills (comma-separated)
                </label>
                <input
                  type="text"
                  placeholder="e.g. python, sql, docker, kubernetes"
                  value={manualRequiredSkills}
                  onChange={(e) => setManualRequiredSkills(e.target.value)}
                  className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-foreground/10"
                />
              </div>
              <div className="col-span-2">
                <label className="text-xs font-medium text-muted-foreground mb-1 block">
                  Optional Skills (comma-separated)
                </label>
                <input
                  type="text"
                  placeholder="e.g. redis, graphql, terraform"
                  value={manualOptionalSkills}
                  onChange={(e) => setManualOptionalSkills(e.target.value)}
                  className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-foreground/10"
                />
              </div>
            </div>
            <div className="flex gap-2 justify-end">
              <Button
                size="sm"
                variant="ghost"
                onClick={() => setCreateMode(null)}
                disabled={creating}
              >
                Cancel
              </Button>
              <Button
                size="sm"
                onClick={handleCreateManual}
                disabled={creating || !manualTitle.trim()}
                className="gap-1.5"
              >
                {creating && <Loader2 className="h-3 w-3 animate-spin" />}
                Create Profile
              </Button>
            </div>
          </motion.div>
        )}

        {loaded && profiles.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, delay: 0.05 }}
          >
            <VirtualizedTable columns={columns} data={profiles} />
          </motion.div>
        )}

        {loaded && profiles.length === 0 && !createMode && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.1 }}
            className="rounded-xl border border-dashed bg-muted/20 py-16 text-center"
          >
            <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-muted/60">
              <Briefcase className="h-5 w-5 text-muted-foreground/60" />
            </div>
            <p className="text-sm font-medium text-foreground/80">
              No job profiles yet
            </p>
            <p className="mt-1 text-sm text-muted-foreground">
              Create a profile or use a template to get started
            </p>
          </motion.div>
        )}
      </motion.div>
    </DashboardLayout>
  )
}
