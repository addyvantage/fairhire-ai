import { ResumeStudioStructuredResume } from "@/lib/api"

export type TemplateName = "ats_classic" | "modern_clean" | "compact_onepager"
export type FontScale = "small" | "normal" | "large"
export type DensityScale = "compact" | "normal" | "airy"
export type AccentTone = "slate" | "indigo" | "emerald"

export type StudioTemplateSettings = {
  font_scale: FontScale
  density: DensityScale
  accent: AccentTone
  show_icons: boolean
  show_sections: {
    summary: boolean
    skills: boolean
    experience: boolean
    projects: boolean
    education: boolean
    certifications: boolean
    awards: boolean
  }
  version_label?: string
}

export type StudioSuggestion = {
  requirement: string
  issue: string
  recommendation: string
  example_bullet: string
  label: "grounded" | "conditional"
}

const DEFAULT_SETTINGS: StudioTemplateSettings = {
  font_scale: "normal",
  density: "normal",
  accent: "slate",
  show_icons: false,
  show_sections: {
    summary: true,
    skills: true,
    experience: true,
    projects: true,
    education: true,
    certifications: true,
    awards: true,
  },
}

export function createEmptyStructuredResume(): ResumeStudioStructuredResume {
  return {
    header: {
      name: "",
      title: "",
      email: "",
      phone: "",
      location: "",
      links: [],
    },
    summary: "",
    skills: {
      categories: [],
    },
    experience: {
      items: [],
    },
    projects: {
      items: [],
    },
    education: {
      items: [],
    },
    certifications: [],
    awards: [],
    ats_keywords: [],
    evidence_map: {},
  }
}

export function cloneStructuredResume(
  resume: ResumeStudioStructuredResume
): ResumeStudioStructuredResume {
  return JSON.parse(JSON.stringify(resume))
}

export function normalizeTemplateSettings(
  settings?: Record<string, unknown> | null
): StudioTemplateSettings {
  const merged = JSON.parse(JSON.stringify(DEFAULT_SETTINGS)) as StudioTemplateSettings
  if (!settings) return merged
  if (typeof settings.font_scale === "string") {
    merged.font_scale = settings.font_scale as FontScale
  }
  if (typeof settings.density === "string") {
    merged.density = settings.density as DensityScale
  }
  if (typeof settings.accent === "string") {
    merged.accent = settings.accent as AccentTone
  }
  if (typeof settings.show_icons === "boolean") {
    merged.show_icons = settings.show_icons
  }
  if (typeof settings.version_label === "string") {
    merged.version_label = settings.version_label.trim()
  }
  if (settings.show_sections && typeof settings.show_sections === "object") {
    merged.show_sections = {
      ...merged.show_sections,
      ...(settings.show_sections as StudioTemplateSettings["show_sections"]),
    }
  }
  return merged
}

function esc(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;")
}

function formatDates(item: { start?: string; end?: string }): string {
  const start = (item.start ?? "").trim()
  const end = (item.end ?? "").trim()
  if (start && end) return `${start} — ${end}`
  return start || end
}

export function renderResumeHtmlClient(
  structuredResume: ResumeStudioStructuredResume,
  templateName: TemplateName,
  templateSettings?: Record<string, unknown> | null
): string {
  const settings = normalizeTemplateSettings(templateSettings)
  const fontSizeMap: Record<FontScale, string> = {
    small: "13px",
    normal: "15px",
    large: "16px",
  }
  const spacingMap: Record<DensityScale, string> = {
    compact: "0.35rem",
    normal: "0.62rem",
    airy: "0.88rem",
  }
  const accentMap: Record<AccentTone, string> = {
    slate: "#334155",
    indigo: "#4338ca",
    emerald: "#047857",
  }
  const fontSize = fontSizeMap[settings.font_scale]
  const sectionSpacing = spacingMap[settings.density]
  const accent = accentMap[settings.accent]

  const template = templateName === "compact_onepager" ? "compact_onepager" : templateName
  const sectionBorder =
    template === "modern_clean"
      ? "1px solid #e5e7eb"
      : template === "compact_onepager"
        ? "1px solid #f1f5f9"
        : "1px solid #e2e8f0"
  const sectionPadding =
    template === "modern_clean"
      ? "0.48rem 0 0.08rem"
      : template === "compact_onepager"
        ? "0.22rem 0 0.08rem"
        : "0.42rem 0 0.1rem"

  const section = (title: string, body: string, key: keyof StudioTemplateSettings["show_sections"]) => {
    if (!settings.show_sections[key] || !body.trim()) return ""
    const iconMap: Record<string, string> = {
      summary: "✦",
      skills: "◆",
      experience: "▣",
      projects: "◉",
      education: "▤",
      certifications: "✓",
      awards: "★",
    }
    const heading = settings.show_icons ? `${iconMap[key] ?? ""} ${title}`.trim() : title
    return (
      `<section style="border-top:${sectionBorder};padding:${sectionPadding};margin-top:${sectionSpacing};">` +
      `<h2 style="margin:0 0 0.4rem;font-size:0.8rem;letter-spacing:.08em;text-transform:uppercase;color:${accent};">${esc(heading)}</h2>` +
      body +
      `</section>`
    )
  }

  const header = structuredResume.header
  const identityBits = [header.email, header.phone, header.location].filter(Boolean)
  const linksHtml = header.links
    .filter((link) => link.url)
    .map((link) => `<a href="${esc(link.url)}" target="_blank">${esc(link.label || "link")}</a>`)
    .join(" · ")

  const summaryHtml = `<p style="margin:0;line-height:1.55;">${esc(structuredResume.summary || "")}</p>`
  const skillsHtml = structuredResume.skills.categories
    .map(
      (category) =>
        `<div style="margin-bottom:.3rem;"><strong>${esc(category.name)}:</strong> ${esc(
          category.items.join(", ")
        )}</div>`
    )
    .join("")
  const experienceHtml = structuredResume.experience.items
    .map((item) => {
      const itemTitle = `${esc(item.role || "")}${item.company ? ` · ${esc(item.company)}` : ""}`
      const bullets = item.bullets
        .map((bullet) => `<li style="margin:.16rem 0;">${esc(bullet)}</li>`)
        .join("")
      return (
        `<article style="margin-bottom:.5rem;">` +
        `<p style="margin:0;font-weight:600;">${itemTitle || esc(item.company || "")}</p>` +
        `${formatDates(item) ? `<p style="margin:0;color:#475569;font-size:.9em;">${esc(formatDates(item))}</p>` : ""}` +
        `<ul style="margin:.28rem 0 0 1rem;padding:0;">${bullets}</ul>` +
        `</article>`
      )
    })
    .join("")
  const projectsHtml = structuredResume.projects.items
    .map((item) => {
      const bullets = item.bullets
        .map((bullet) => `<li style="margin:.16rem 0;">${esc(bullet)}</li>`)
        .join("")
      return (
        `<article style="margin-bottom:.5rem;">` +
        `<p style="margin:0;font-weight:600;">${esc(item.name)}</p>` +
        `${item.link ? `<p style="margin:0;color:#475569;font-size:.9em;">${esc(item.link)}</p>` : ""}` +
        `<ul style="margin:.28rem 0 0 1rem;padding:0;">${bullets}</ul>` +
        `</article>`
      )
    })
    .join("")
  const educationHtml = structuredResume.education.items
    .map(
      (item) =>
        `<article style="margin-bottom:.45rem;"><p style="margin:0;font-weight:600;">${esc(item.school)}</p>` +
        `${item.degree ? `<p style="margin:0;color:#475569;">${esc(item.degree)}</p>` : ""}` +
        `${formatDates(item) ? `<p style="margin:0;color:#475569;font-size:.9em;">${esc(formatDates(item))}</p>` : ""}` +
        `</article>`
    )
    .join("")
  const certificationsHtml = `<ul style="margin:0 0 0 1rem;padding:0;">${structuredResume.certifications
    .map((item) => `<li>${esc(item)}</li>`)
    .join("")}</ul>`
  const awardsHtml = `<ul style="margin:0 0 0 1rem;padding:0;">${structuredResume.awards
    .map((item) => `<li>${esc(item)}</li>`)
    .join("")}</ul>`

  return (
    "<!doctype html><html><head><meta charset='utf-8'/>" +
    "<meta name='viewport' content='width=device-width, initial-scale=1'/>" +
    "<title>Resume Preview</title></head>" +
    `<body style="margin:0;background:#f8fafc;font-family:Inter,Segoe UI,Arial,sans-serif;color:#0f172a;font-size:${fontSize};">` +
    `<main style="max-width:${template === "compact_onepager" ? "760px" : "860px"};margin:0 auto;background:white;padding:${template === "compact_onepager" ? "1.3rem 1.4rem 1rem" : "2rem 2rem 1.5rem"};">` +
    `<h1 style="margin:0;font-size:${template === "compact_onepager" ? "1.42rem" : "1.72rem"};">${esc(header.name)}</h1>` +
    `${header.title ? `<p style="margin:.3rem 0 .08rem;color:${accent};font-weight:600;">${esc(header.title)}</p>` : ""}` +
    `<p style="margin:0;color:#475569;">${identityBits.map(esc).join(" · ")}${
      linksHtml && identityBits.length > 0 ? " · " : ""
    }${linksHtml}</p>` +
    section("Summary", summaryHtml, "summary") +
    section("Skills", skillsHtml, "skills") +
    section("Experience", experienceHtml, "experience") +
    section("Projects", projectsHtml, "projects") +
    section("Education", educationHtml, "education") +
    section("Certifications", certificationsHtml, "certifications") +
    section("Awards", awardsHtml, "awards") +
    "</main></body></html>"
  )
}

export type StudioDiff = {
  addedBullets: string[]
  removedBullets: string[]
  modifiedBullets: Array<{ from: string; to: string }>
  keywordsAdded: string[]
  skillsAdded: string[]
  skillsRemoved: string[]
  sectionsChanged: string[]
  bulletDelta: number
}

function normalizeBullet(value: string): string {
  return value.trim().toLowerCase()
}

function collectBullets(resume: ResumeStudioStructuredResume): string[] {
  const bullets: string[] = []
  resume.experience.items.forEach((item) => bullets.push(...item.bullets))
  resume.projects.items.forEach((item) => bullets.push(...item.bullets))
  return bullets.map((bullet) => bullet.trim()).filter(Boolean)
}

function jaccardSimilarity(a: string, b: string): number {
  const left = new Set(a.toLowerCase().split(/\W+/).filter((token) => token.length > 2))
  const right = new Set(b.toLowerCase().split(/\W+/).filter((token) => token.length > 2))
  if (left.size === 0 || right.size === 0) return 0
  const intersection = [...left].filter((token) => right.has(token)).length
  const union = new Set([...left, ...right]).size
  return union === 0 ? 0 : intersection / union
}

export function diffStructuredResumes(
  base: ResumeStudioStructuredResume,
  current: ResumeStudioStructuredResume
): StudioDiff {
  const baseBullets = collectBullets(base)
  const currentBullets = collectBullets(current)
  const baseSet = new Set(baseBullets.map(normalizeBullet))
  const currentSet = new Set(currentBullets.map(normalizeBullet))

  const addedBullets = currentBullets.filter((bullet) => !baseSet.has(normalizeBullet(bullet)))
  const removedBullets = baseBullets.filter((bullet) => !currentSet.has(normalizeBullet(bullet)))

  const modifiedBullets: Array<{ from: string; to: string }> = []
  const unmatchedAdded = [...addedBullets]
  const unmatchedRemoved = [...removedBullets]
  for (let i = unmatchedRemoved.length - 1; i >= 0; i -= 1) {
    const removed = unmatchedRemoved[i]
    let bestIndex = -1
    let bestScore = 0
    for (let j = 0; j < unmatchedAdded.length; j += 1) {
      const added = unmatchedAdded[j]
      const score = jaccardSimilarity(removed, added)
      if (score > bestScore) {
        bestScore = score
        bestIndex = j
      }
    }
    if (bestIndex >= 0 && bestScore >= 0.36) {
      modifiedBullets.push({ from: removed, to: unmatchedAdded[bestIndex] })
      unmatchedRemoved.splice(i, 1)
      unmatchedAdded.splice(bestIndex, 1)
    }
  }

  const baseSkills = new Set(
    base.skills.categories.flatMap((category) => category.items.map((item) => item.trim().toLowerCase())).filter(Boolean)
  )
  const currentSkills = new Set(
    current.skills.categories
      .flatMap((category) => category.items.map((item) => item.trim().toLowerCase()))
      .filter(Boolean)
  )
  const skillsAdded = [...currentSkills].filter((item) => !baseSkills.has(item))
  const skillsRemoved = [...baseSkills].filter((item) => !currentSkills.has(item))

  const atsBase = new Set(base.ats_keywords.map((item) => item.toLowerCase()))
  const keywordsAdded = current.ats_keywords
    .map((item) => item.toLowerCase())
    .filter((item) => !atsBase.has(item))

  const sectionsChanged = ["summary", "skills", "experience", "projects", "education", "certifications", "awards"].filter(
    (section) =>
      JSON.stringify(base[section as keyof ResumeStudioStructuredResume]) !==
      JSON.stringify(current[section as keyof ResumeStudioStructuredResume])
  )

  return {
    addedBullets: unmatchedAdded,
    removedBullets: unmatchedRemoved,
    modifiedBullets,
    keywordsAdded,
    skillsAdded,
    skillsRemoved,
    sectionsChanged,
    bulletDelta: currentBullets.length - baseBullets.length,
  }
}

export function collectResumeDiagnostics(resume: ResumeStudioStructuredResume): {
  wordCount: number
  sectionCount: number
  skillsCount: number
  warnings: string[]
} {
  const text = [
    resume.summary,
    ...collectBullets(resume),
    ...resume.education.items.map((item) => `${item.school} ${item.degree}`.trim()),
  ]
    .join(" ")
    .trim()
  const wordCount = text.length > 0 ? text.split(/\s+/).length : 0
  const skills = resume.skills.categories.flatMap((category) => category.items.map((item) => item.trim())).filter(Boolean)
  const sectionCount = [
    resume.summary.trim() ? 1 : 0,
    resume.skills.categories.length > 0 ? 1 : 0,
    resume.experience.items.length > 0 ? 1 : 0,
    resume.projects.items.length > 0 ? 1 : 0,
    resume.education.items.length > 0 ? 1 : 0,
    resume.certifications.length > 0 ? 1 : 0,
    resume.awards.length > 0 ? 1 : 0,
  ].reduce((sum, value) => sum + value, 0)
  const warnings: string[] = []
  if (!resume.summary.trim()) warnings.push("Summary is empty.")
  if (resume.experience.items.some((item) => !item.start && !item.end)) {
    warnings.push("Some experience items are missing dates.")
  }
  if (resume.experience.items.some((item) => item.bullets.some((bullet) => bullet.length > 180))) {
    warnings.push("Some bullets are too long for ATS readability.")
  }
  const normalizedSkills = skills.map((item) => item.toLowerCase())
  const duplicateSkills = normalizedSkills.filter(
    (item, index) => normalizedSkills.indexOf(item) !== index
  )
  if (duplicateSkills.length > 0) warnings.push("Duplicate skills detected.")
  if (wordCount > 900) warnings.push("Resume appears long. Consider one-page focus.")
  if (wordCount < 180) warnings.push("Resume may be too short for recruiter context.")

  return {
    wordCount,
    sectionCount,
    skillsCount: skills.length,
    warnings,
  }
}

export function groupSuggestions(scoreSnapshot: Record<string, unknown> | null): {
  highImpact: string[]
  missingKeywords: string[]
  groundedRewrites: StudioSuggestion[]
  conditionalRewrites: StudioSuggestion[]
  missingEvidence: string[]
  atsMap: Array<{ keyword: string; status: string; location_hint: string }>
} {
  const fastestFixes = ((scoreSnapshot?.fastest_fixes as string[]) ?? []).filter(Boolean)
  const missingEvidence = ((scoreSnapshot?.missing_evidence as string[]) ?? []).filter(Boolean)
  const atsMapRaw =
    (scoreSnapshot?.ats_keyword_map as Array<{
      keyword?: string
      status?: string
      location_hint?: string
    }>) ?? []
  const atsMap = atsMapRaw
    .filter((item) => item.keyword)
    .map((item) => ({
      keyword: item.keyword ?? "",
      status: item.status ?? "missing",
      location_hint: item.location_hint ?? "Add in experience bullets",
    }))
  const missingKeywords = atsMap.filter((item) => item.status === "missing").map((item) => item.keyword)

  const rewritesRaw =
    (scoreSnapshot?.rewrite_suggestions as Array<{
      requirement?: string
      issue?: string
      recommendation?: string
      example_bullet?: string
    }>) ?? []

  const classified = rewritesRaw
    .filter((entry) => (entry.recommendation ?? entry.example_bullet ?? "").trim().length > 0)
    .map((entry) => {
      const example = entry.example_bullet?.trim() ?? ""
      const isConditional = example.toLowerCase().startsWith("[add if true]")
      return {
        requirement: entry.requirement ?? "Requirement",
        issue: entry.issue ?? "",
        recommendation: entry.recommendation ?? "",
        example_bullet: example,
        label: isConditional ? "conditional" : "grounded",
      } satisfies StudioSuggestion
    })

  return {
    highImpact: fastestFixes.slice(0, 5),
    missingKeywords,
    groundedRewrites: classified.filter((item) => item.label === "grounded"),
    conditionalRewrites: classified.filter((item) => item.label === "conditional"),
    missingEvidence,
    atsMap,
  }
}

function scoreBulletImpact(bullet: string): number {
  const lower = bullet.toLowerCase()
  let score = 0
  if (/\d/.test(bullet)) score += 2
  if (/%|\$|kpi|roi|revenue|cost|reduced|improved|increased|decreased/.test(lower)) score += 2
  if (/led|built|implemented|designed|optimized|launched|automated/.test(lower)) score += 1
  return score
}

export function bulletImpactLevel(bullet: string): "low" | "medium" | "high" {
  const score = scoreBulletImpact(bullet)
  if (score >= 4) return "high"
  if (score >= 2) return "medium"
  return "low"
}

export function applySuggestionToResume(
  resume: ResumeStudioStructuredResume,
  suggestion: StudioSuggestion,
  proofText?: string
): ResumeStudioStructuredResume {
  const next = cloneStructuredResume(resume)
  const bulletBase = suggestion.example_bullet || suggestion.recommendation || suggestion.issue
  const normalized = bulletBase.replace(/^\[add if true\]\s*/i, "").trim()
  const bullet = proofText?.trim()
    ? `${normalized} (${proofText.trim()})`
    : normalized

  const tokens = suggestion.requirement
    .toLowerCase()
    .split(/\W+/)
    .filter((token) => token.length > 3)
  let targetIndex = 0
  let bestScore = -1
  next.experience.items.forEach((item, index) => {
    const text = `${item.role} ${item.company} ${item.bullets.join(" ")}`.toLowerCase()
    const score = tokens.reduce((sum, token) => sum + (text.includes(token) ? 1 : 0), 0)
    if (score > bestScore) {
      bestScore = score
      targetIndex = index
    }
  })

  if (next.experience.items.length === 0) {
    next.experience.items.push({
      company: "",
      role: "",
      location: "",
      start: "",
      end: "",
      bullets: [bullet],
      tech: [],
    })
  } else {
    next.experience.items[targetIndex].bullets.push(bullet)
  }
  return next
}
