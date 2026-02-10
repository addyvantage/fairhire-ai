"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import { useRouter } from "next/navigation"
import { AnimatePresence, motion } from "framer-motion"
import {
  Briefcase,
  Building2,
  Loader2,
  Plus,
  Sparkles,
  Trash2,
  X,
} from "lucide-react"
import { useAuth } from "@/lib/auth-context"
import {
  JobProfile,
  JobTargetPreview,
  createJobProfile,
  deleteJobProfile,
  listJobProfiles,
  parseJobProfilePreview,
} from "@/lib/api"
import { DashboardLayout } from "@/components/layout/dashboard-layout"
import { Button } from "@/components/ui/button"
import { EmptyState } from "@/components/ui/empty-state"
import { Input } from "@/components/ui/input"
import { PageTransition } from "@/components/ui/page-transition"
import { SegmentedControl } from "@/components/ui/segmented-control"
import { Skeleton } from "@/components/ui/skeleton"
import { useToast } from "@/components/ui/use-toast"
import { transitions } from "@/lib/motion"

type CreateMode = "paste" | "manual"
type ViewMode = "grid" | "list"

function inferIndustry(profile: JobProfile) {
  const source = `${profile.title} ${profile.raw_description ?? ""}`.toLowerCase()
  if (source.includes("finance") || source.includes("analyst")) return "Finance"
  if (source.includes("health") || source.includes("clinical")) return "Healthcare"
  if (source.includes("sales") || source.includes("marketing")) return "Sales & Marketing"
  if (source.includes("data") || source.includes("engineer") || source.includes("software")) return "Technology"
  if (source.includes("operations") || source.includes("supply")) return "Operations"
  return "General"
}

function JobProfilesSkeleton() {
  return (
    <DashboardLayout title="Job Profiles" description="Configure role scorecards for targeted matching.">
      <div className="mx-auto w-full max-w-6xl space-y-6">
        <Skeleton className="h-10 w-40 rounded-xl" />
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }).map((_, index) => (
            <div key={index} className="surface-card space-y-4 p-5">
              <Skeleton className="h-4 w-2/3" />
              <Skeleton className="h-3 w-1/3" />
              <Skeleton className="h-20 w-full" />
            </div>
          ))}
        </div>
      </div>
    </DashboardLayout>
  )
}

export default function JobProfilesPage() {
  const { token, isAuthenticated, isLoading } = useAuth()
  const { toast } = useToast()
  const router = useRouter()

  const [profiles, setProfiles] = useState<JobProfile[]>([])
  const [loaded, setLoaded] = useState(false)
  const [creating, setCreating] = useState(false)
  const [openModal, setOpenModal] = useState(false)
  const [createMode, setCreateMode] = useState<CreateMode>("paste")
  const [viewMode, setViewMode] = useState<ViewMode>("grid")

  const [pasteTitle, setPasteTitle] = useState("")
  const [pasteText, setPasteText] = useState("")
  const [parsePreview, setParsePreview] = useState<JobTargetPreview | null>(null)
  const [previewLoading, setPreviewLoading] = useState(false)
  const [previewError, setPreviewError] = useState<string | null>(null)

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
  }, [isAuthenticated, isLoading, router])

  const fetchProfiles = useCallback(async () => {
    if (!token) return
    try {
      const entries = await listJobProfiles(token)
      setProfiles(entries)
      setLoaded(true)
    } catch {
      setProfiles([])
      setLoaded(true)
    }
  }, [token])

  useEffect(() => {
    fetchProfiles()
  }, [fetchProfiles])

  useEffect(() => {
    if (!token || !openModal || createMode !== "paste") {
      setPreviewLoading(false)
      setPreviewError(null)
      return
    }
    if (!pasteTitle.trim() || pasteText.trim().length < 80) {
      setParsePreview(null)
      setPreviewLoading(false)
      setPreviewError(null)
      return
    }

    let cancelled = false
    const timeout = setTimeout(async () => {
      setPreviewLoading(true)
      setPreviewError(null)
      try {
        const preview = await parseJobProfilePreview(token, {
          title: pasteTitle.trim(),
          raw_description: pasteText.trim(),
        })
        if (!cancelled) {
          setParsePreview(preview)
        }
      } catch (error) {
        if (!cancelled) {
          setParsePreview(null)
          setPreviewError((error as Error).message)
        }
      } finally {
        if (!cancelled) {
          setPreviewLoading(false)
        }
      }
    }, 450)

    return () => {
      cancelled = true
      clearTimeout(timeout)
    }
  }, [createMode, openModal, pasteText, pasteTitle, token])

  const sortedProfiles = useMemo(
    () =>
      [...profiles].sort((a, b) => {
        if (a.is_template === b.is_template) return a.title.localeCompare(b.title)
        return a.is_template ? 1 : -1
      }),
    [profiles]
  )

  async function handleCreatePaste() {
    if (!token || !pasteTitle.trim()) return
    setCreating(true)
    try {
      await createJobProfile(token, {
        title: pasteTitle.trim(),
        raw_description: pasteText.trim() || undefined,
      })
      toast({ title: "Profile created", description: pasteTitle.trim() })
      setPasteTitle("")
      setPasteText("")
      setOpenModal(false)
      fetchProfiles()
    } catch (error) {
      toast({
        title: "Create failed",
        description: (error as Error).message,
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
      const requiredSkills = manualRequiredSkills
        .split(",")
        .map((entry) => entry.trim())
        .filter(Boolean)
      const optionalSkills = manualOptionalSkills
        .split(",")
        .map((entry) => entry.trim())
        .filter(Boolean)

      await createJobProfile(token, {
        title: manualTitle.trim(),
        seniority_level: manualSeniority || undefined,
        required_skills: requiredSkills.length > 0 ? requiredSkills : undefined,
        optional_skills: optionalSkills.length > 0 ? optionalSkills : undefined,
        years_experience_min: manualExpMin ? Number(manualExpMin) : undefined,
        years_experience_max: manualExpMax ? Number(manualExpMax) : undefined,
      })

      toast({ title: "Profile created", description: manualTitle.trim() })
      setManualTitle("")
      setManualSeniority("")
      setManualRequiredSkills("")
      setManualOptionalSkills("")
      setManualExpMin("")
      setManualExpMax("")
      setOpenModal(false)
      fetchProfiles()
    } catch (error) {
      toast({
        title: "Create failed",
        description: (error as Error).message,
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
    } catch (error) {
      toast({
        title: "Delete failed",
        description: (error as Error).message,
        variant: "destructive",
      })
    }
  }

  if (isLoading || !isAuthenticated) return <JobProfilesSkeleton />

  return (
    <DashboardLayout
      title="Job Profiles"
      description="Build reusable role scorecards and target each analysis with intent."
      actions={
        <div className="flex items-center gap-2">
          <SegmentedControl
            options={[
              { label: "Grid", value: "grid" },
              { label: "List", value: "list" },
            ]}
            value={viewMode}
            onChange={setViewMode}
          />
          <Button size="sm" onClick={() => setOpenModal(true)}>
            <Plus className="h-4 w-4" />
            Create profile
          </Button>
        </div>
      }
    >
      <PageTransition className="mx-auto w-full max-w-6xl">
        {loaded && sortedProfiles.length === 0 ? (
          <EmptyState
            icon={<Sparkles className="h-5 w-5" />}
            title="No job profiles yet"
            description="Create your first profile to unlock targeted role matching and clearer hiring recommendations."
            action={<Button onClick={() => setOpenModal(true)}>Create profile</Button>}
          />
        ) : null}

        {sortedProfiles.length > 0 && viewMode === "grid" && (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {sortedProfiles.map((profile) => (
              <JobProfileCard key={profile.id} profile={profile} onDelete={handleDelete} />
            ))}
          </div>
        )}

        {sortedProfiles.length > 0 && viewMode === "list" && (
          <div className="surface-card overflow-hidden">
            <div className="grid grid-cols-5 border-b bg-muted/70 px-4 py-3 text-xs font-semibold uppercase tracking-[0.08em] text-muted-foreground">
              <span className="col-span-2">Role</span>
              <span>Industry</span>
              <span>Seniority</span>
              <span className="text-right">Skills</span>
            </div>
            <div className="divide-y divide-border/80">
              {sortedProfiles.map((profile) => (
                <div key={profile.id} className="grid grid-cols-5 items-center gap-3 px-4 py-3">
                  <div className="col-span-2 flex items-center gap-3">
                    <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-muted">
                      <Briefcase className="h-4 w-4 text-muted-foreground" />
                    </div>
                    <div>
                      <p className="text-sm font-medium text-foreground">{profile.title}</p>
                      {profile.is_template && (
                        <span className="rounded-full bg-primary-soft px-2 py-0.5 text-[11px] font-medium text-primary">
                          Template
                        </span>
                      )}
                    </div>
                  </div>
                  <p className="text-sm text-muted-foreground">{inferIndustry(profile)}</p>
                  <p className="text-sm capitalize text-muted-foreground">
                    {profile.seniority_level ?? "Not set"}
                  </p>
                  <div className="flex items-center justify-end gap-3">
                    <p className="text-sm font-medium tabular-nums text-foreground">
                      {(profile.required_skills?.length ?? 0) + (profile.optional_skills?.length ?? 0)}
                    </p>
                    {!profile.is_template && (
                      <button
                        type="button"
                        onClick={() => handleDelete(profile.id)}
                        className="rounded-md p-1 text-muted-foreground hover:bg-muted hover:text-destructive"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </PageTransition>

      <AnimatePresence>
        {openModal && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-40 flex items-center justify-center bg-slate-900/25 px-4 backdrop-blur-sm"
            onClick={() => setOpenModal(false)}
          >
            <motion.div
              initial={{ opacity: 0, y: 10, scale: 0.985 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 10, scale: 0.985 }}
              transition={transitions.base}
              className="w-full max-w-2xl rounded-[var(--radius-lg)] border border-border bg-card shadow-[var(--shadow-lg)]"
              onClick={(event) => event.stopPropagation()}
            >
              <div className="flex items-start justify-between border-b border-border px-6 py-5">
                <div>
                  <h2 className="text-lg font-semibold text-foreground">Create job profile</h2>
                  <p className="mt-1 text-sm text-muted-foreground">
                    Paste a JD or configure a profile manually.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setOpenModal(false)}
                  className="rounded-lg p-1.5 text-muted-foreground hover:bg-muted"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>

              <div className="space-y-5 px-6 py-5">
                <SegmentedControl
                  options={[
                    { label: "Paste JD", value: "paste" },
                    { label: "Build manually", value: "manual" },
                  ]}
                  value={createMode}
                  onChange={setCreateMode}
                />

                {createMode === "paste" ? (
                  <div className="space-y-4">
                    <Input
                      placeholder="Role title (e.g. Financial Analyst)"
                      value={pasteTitle}
                      onChange={(event) => setPasteTitle(event.target.value)}
                    />
                    <textarea
                      className="min-h-44 w-full rounded-[calc(var(--radius)-3px)] border border-input bg-background px-3.5 py-3 text-sm outline-none focus:ring-2 focus:ring-ring/30"
                      placeholder="Paste full job description here…"
                      value={pasteText}
                      onChange={(event) => setPasteText(event.target.value)}
                    />
                    <div className="rounded-xl border border-border/80 bg-muted/20 p-4">
                      <div className="flex items-center justify-between gap-3">
                        <p className="text-sm font-semibold text-foreground">Role extraction preview</p>
                        {previewLoading && (
                          <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
                            <Loader2 className="h-3.5 w-3.5 animate-spin" />
                            Parsing job description…
                          </span>
                        )}
                      </div>
                      {previewError ? (
                        <p className="mt-2 text-xs text-destructive">{previewError}</p>
                      ) : null}
                      {!parsePreview && !previewLoading && !previewError ? (
                        <p className="mt-2 text-xs text-muted-foreground">
                          Paste a full job description to preview extracted role intelligence.
                        </p>
                      ) : null}
                      {parsePreview ? (
                        <div className="mt-3 space-y-3">
                          <div className="grid gap-2 sm:grid-cols-3">
                            <PreviewStat label="Seniority" value={parsePreview.seniority_level} />
                            <PreviewStat
                              label="Experience"
                              value={
                                parsePreview.years_experience_required.min != null
                                  ? `${parsePreview.years_experience_required.min}-${parsePreview.years_experience_required.max ?? "?"} yrs`
                                  : "Not specified"
                              }
                            />
                            <PreviewStat
                              label="Core tools"
                              value={`${parsePreview.required_skills.length} required`}
                            />
                          </div>
                          <div className="grid gap-2 sm:grid-cols-3">
                            <PreviewStat label="Archetype" value={parsePreview.role_archetype.replace("_", " ")} />
                            <PreviewStat label="Responsibilities" value={`${parsePreview.responsibilities.length}`} />
                            <PreviewStat label="Hard requirements" value={`${parsePreview.requirements_hard.length}`} />
                          </div>
                          <div className="space-y-1">
                            <p className="text-xs font-medium uppercase tracking-[0.08em] text-muted-foreground">
                              Top hard requirements
                            </p>
                            <div className="flex flex-wrap gap-1.5">
                              {parsePreview.hard_requirements.slice(0, 4).map((item) => (
                                <span
                                  key={item}
                                  className="rounded-full bg-primary-soft px-2.5 py-1 text-xs text-primary"
                                >
                                  {item}
                                </span>
                              ))}
                              {parsePreview.hard_requirements.length === 0 && (
                                <span className="text-xs text-muted-foreground">No hard requirements detected yet.</span>
                              )}
                            </div>
                          </div>
                        </div>
                      ) : null}
                    </div>
                  </div>
                ) : (
                  <div className="grid gap-4 md:grid-cols-2">
                    <div className="md:col-span-2">
                      <Input
                        placeholder="Role title"
                        value={manualTitle}
                        onChange={(event) => setManualTitle(event.target.value)}
                      />
                    </div>
                    <select
                      value={manualSeniority}
                      onChange={(event) => setManualSeniority(event.target.value)}
                      className="h-10 rounded-[calc(var(--radius)-3px)] border border-input bg-background px-3.5 text-sm capitalize outline-none focus:ring-2 focus:ring-ring/30"
                    >
                      <option value="">Select seniority</option>
                      <option value="intern">Intern</option>
                      <option value="junior">Junior</option>
                      <option value="mid">Mid-level</option>
                      <option value="senior">Senior</option>
                      <option value="lead">Lead</option>
                      <option value="staff">Staff</option>
                      <option value="principal">Principal</option>
                    </select>
                    <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-2">
                      <Input
                        type="number"
                        placeholder="Min years"
                        value={manualExpMin}
                        onChange={(event) => setManualExpMin(event.target.value)}
                      />
                      <span className="text-sm text-muted-foreground">to</span>
                      <Input
                        type="number"
                        placeholder="Max years"
                        value={manualExpMax}
                        onChange={(event) => setManualExpMax(event.target.value)}
                      />
                    </div>
                    <div className="md:col-span-2">
                      <Input
                        placeholder="Required skills (comma-separated)"
                        value={manualRequiredSkills}
                        onChange={(event) => setManualRequiredSkills(event.target.value)}
                      />
                    </div>
                    <div className="md:col-span-2">
                      <Input
                        placeholder="Optional skills (comma-separated)"
                        value={manualOptionalSkills}
                        onChange={(event) => setManualOptionalSkills(event.target.value)}
                      />
                    </div>
                  </div>
                )}
              </div>

              <div className="flex justify-end gap-2 border-t border-border px-6 py-4">
                <Button variant="outline" onClick={() => setOpenModal(false)} disabled={creating}>
                  Cancel
                </Button>
                <Button
                  onClick={createMode === "paste" ? handleCreatePaste : handleCreateManual}
                  disabled={
                    creating || (createMode === "paste" ? !pasteTitle.trim() : !manualTitle.trim())
                  }
                >
                  {creating && <Loader2 className="h-4 w-4 animate-spin" />}
                  Create profile
                </Button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </DashboardLayout>
  )
}

function PreviewStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border/70 bg-background px-3 py-2">
      <p className="text-[11px] uppercase tracking-[0.08em] text-muted-foreground">{label}</p>
      <p className="mt-1 text-sm font-medium text-foreground">{value}</p>
    </div>
  )
}

function JobProfileCard({
  profile,
  onDelete,
}: {
  profile: JobProfile
  onDelete: (profileId: number) => void
}) {
  const skillCount = (profile.required_skills?.length ?? 0) + (profile.optional_skills?.length ?? 0)

  return (
    <motion.article whileHover={{ y: -2 }} className="surface-card space-y-5 p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-base font-semibold text-foreground">{profile.title}</h3>
            {profile.is_template && (
              <span className="rounded-full bg-primary-soft px-2 py-0.5 text-[11px] font-medium text-primary">
                Template
              </span>
            )}
          </div>
          <p className="mt-1 text-sm text-muted-foreground">{inferIndustry(profile)}</p>
        </div>
        {!profile.is_template && (
          <button
            type="button"
            onClick={() => onDelete(profile.id)}
            className="rounded-md p-1 text-muted-foreground hover:bg-muted hover:text-destructive"
          >
            <Trash2 className="h-4 w-4" />
          </button>
        )}
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="rounded-lg border border-border/80 bg-muted/40 px-3 py-2">
          <p className="text-xs uppercase tracking-[0.08em] text-muted-foreground">Seniority</p>
          <p className="mt-1 text-sm font-medium capitalize text-foreground">
            {profile.seniority_level ?? "Not set"}
          </p>
        </div>
        <div className="rounded-lg border border-border/80 bg-muted/40 px-3 py-2">
          <p className="text-xs uppercase tracking-[0.08em] text-muted-foreground">Skill count</p>
          <p className="mt-1 text-sm font-medium text-foreground tabular-nums">{skillCount}</p>
        </div>
      </div>

      <div className="space-y-2">
        <p className="text-xs font-semibold uppercase tracking-[0.08em] text-muted-foreground">
          Role highlights
        </p>
        <div className="flex flex-wrap gap-1.5">
          {(profile.required_skills ?? []).slice(0, 5).map((skill) => (
            <span key={skill} className="rounded-full bg-muted px-2.5 py-1 text-xs text-muted-foreground">
              {skill}
            </span>
          ))}
          {skillCount === 0 && (
            <span className="rounded-full bg-muted px-2.5 py-1 text-xs text-muted-foreground">
              Add skills for sharper analysis
            </span>
          )}
        </div>
      </div>

      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span className="inline-flex items-center gap-1">
          <Building2 className="h-3.5 w-3.5" />
          {inferIndustry(profile)}
        </span>
        <span>{profile.source === "template" ? "Template source" : "Custom profile"}</span>
      </div>
    </motion.article>
  )
}
