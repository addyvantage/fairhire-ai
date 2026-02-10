"use client"

import { useEffect, useState } from "react"
import { Briefcase, Search, X } from "lucide-react"
import { motion, AnimatePresence } from "framer-motion"
import { type JobProfile } from "@/lib/api"
import { transitions } from "@/lib/motion"

type Props = {
  profiles: JobProfile[]
  lastUsedProfileId: number | null
  onSelect: (profile: JobProfile) => void
  onClose: () => void
}

export function JobProfileSelector({
  profiles,
  lastUsedProfileId,
  onSelect,
  onClose,
}: Props) {
  const [search, setSearch] = useState("")

  // Close on Escape
  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose()
    }
    window.addEventListener("keydown", handleKey)
    return () => window.removeEventListener("keydown", handleKey)
  }, [onClose])

  const filtered = profiles.filter(
    (p) =>
      p.title.toLowerCase().includes(search.toLowerCase()) ||
      (p.seniority_level ?? "").toLowerCase().includes(search.toLowerCase())
  )

  const templates = filtered.filter((p) => p.is_template)
  const userProfiles = filtered.filter((p) => !p.is_template)

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/25 backdrop-blur-sm"
        onClick={onClose}
      >
        <motion.div
          initial={{ opacity: 0, scale: 0.95, y: 10 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: 10 }}
          transition={transitions.fast}
          className="relative w-full max-w-2xl rounded-[var(--radius-lg)] border border-border bg-card shadow-[var(--shadow-lg)]"
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div className="flex items-center justify-between border-b border-border/80 px-6 py-5">
            <div>
              <h2 className="text-base font-semibold text-foreground">
                Select Job Profile
              </h2>
              <p className="mt-1 text-sm text-muted-foreground">
                Choose a target role to score the resume against
              </p>
            </div>
            <button
              onClick={onClose}
              className="rounded-lg p-1.5 text-muted-foreground hover:bg-muted/60"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          {/* Search */}
          <div className="border-b border-border/80 px-6 py-4">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <input
                type="text"
                placeholder="Search profiles..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                autoFocus
                className="h-10 w-full rounded-xl border border-input bg-background py-2 pl-10 pr-3 text-sm outline-none focus:ring-2 focus:ring-ring/30"
              />
            </div>
          </div>

          {/* Profile list */}
          <div className="max-h-[420px] overflow-y-auto p-3">
            {userProfiles.length > 0 && (
              <div className="mb-3">
                <p className="px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.1em] text-muted-foreground">
                  Your Profiles
                </p>
                {userProfiles.map((profile) => (
                  <ProfileCard
                    key={profile.id}
                    profile={profile}
                    isLastUsed={profile.id === lastUsedProfileId}
                    onSelect={() => onSelect(profile)}
                  />
                ))}
              </div>
            )}

            {templates.length > 0 && (
              <div>
                <p className="px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.1em] text-muted-foreground">
                  Templates
                </p>
                {templates.map((profile) => (
                  <ProfileCard
                    key={profile.id}
                    profile={profile}
                    isLastUsed={profile.id === lastUsedProfileId}
                    onSelect={() => onSelect(profile)}
                  />
                ))}
              </div>
            )}

            {filtered.length === 0 && (
              <div className="py-8 text-center">
                <p className="text-sm text-muted-foreground">No matching profiles</p>
              </div>
            )}
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  )
}

function ProfileCard({
  profile,
  isLastUsed,
  onSelect,
}: {
  profile: JobProfile
  isLastUsed: boolean
  onSelect: () => void
}) {
  return (
    <button
      onClick={onSelect}
      className="mb-1 flex w-full items-center gap-3 rounded-xl border border-transparent px-3 py-2.5 text-left hover:border-border hover:bg-muted/30"
    >
      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-muted">
        <Briefcase className="h-3.5 w-3.5 text-muted-foreground" />
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-foreground truncate">
            {profile.title}
          </span>
          {isLastUsed && (
            <span className="shrink-0 rounded-full bg-primary-soft px-2 py-0.5 text-[10px] font-medium text-primary">
              Last used
            </span>
          )}
        </div>
        <div className="mt-0.5 flex items-center gap-2">
          {profile.seniority_level && (
            <span className="text-xs text-muted-foreground capitalize">
              {profile.seniority_level}
            </span>
          )}
          <span className="text-xs text-muted-foreground/60">
            {profile.required_skills?.length ?? 0} skills
          </span>
        </div>
      </div>
    </button>
  )
}
