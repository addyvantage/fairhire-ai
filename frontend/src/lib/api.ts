const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export type LoginResponse = {
  access_token: string;
  token_type: string;
};

export type Resume = {
  id: number;
  original_filename: string;
  parsed_text: string;
  created_at: string;
};

export type DashboardStats = {
  total_resumes: number;
  total_analyses: number;
  completed_analyses: number;
  avg_match_score: number;
  completion_rate: number;
  total_job_profiles: number;
};

export type AnalysisQueued = {
  analysis_id: number;
  status: string;
  created_at: string;
};

export type JobProfile = {
  id: number;
  user_id: number | null;
  title: string;
  normalized_title: string | null;
  seniority_level: string | null;
  required_skills: string[] | null;
  optional_skills: string[] | null;
  responsibilities: string[] | null;
  years_experience_min: number | null;
  years_experience_max: number | null;
  source: string;
  raw_description: string | null;
  is_template: boolean;
  created_at: string;
};

export type JobMatchResult = {
  overall_match_score: number;
  skill_match_score: number;
  experience_match_score: number;
  role_alignment_score: number;
  seniority_fit_score: number;
  quality_score: number;
  gaps: string[];
  strengths: string[];
  explanation_summary: string;
  recruiter_verdict?: string;
  rejection_risks?: string[];
  fastest_fixes?: string[];
  matched_requirements?: Array<{
    requirement: string;
    category: "required" | "optional";
    matched: boolean;
    confidence: number;
    evidence: string[];
  }>;
  missing_requirements?: Array<{
    requirement: string;
    category: "required" | "optional";
    matched: boolean;
    confidence: number;
    evidence: string[];
  }>;
  missing_evidence?: string[];
  rewrite_suggestions?: Array<{
    requirement: string;
    issue: string;
    recommendation: string;
    example_bullet: string;
  }>;
  ats_keyword_map?: Array<{
    keyword: string;
    status: "matched" | "missing";
    location_hint: string;
    evidence: string[];
  }>;
  resume_vs_jd_comparison?: Array<{
    cluster: string;
    jd_items: number;
    matched_items: number;
    coverage_score: number;
  }>;
  dimension_scores?: Array<{
    key: string;
    label: string;
    score: number;
    weight: number;
  }>;
  details: {
    resume_skills: string[];
    matched_required: string[];
    matched_optional: string[];
    missing_required: string[];
    extra_resume_skills: string[];
    experience_years_detected: number;
    cosine_similarity: number;
    role_family?: string;
    weights?: Record<string, number>;
    domain_hits?: string[];
    domain_missing?: string[];
    evidence_map?: Record<string, string[]>;
  };
};

export type JobTargetPreview = {
  role_title: string;
  normalized_title: string;
  role_archetype: string;
  seniority_level: string;
  years_experience_required: {
    min: number | null;
    max: number | null;
  };
  company_context: string[];
  role_summary: string[];
  constraints: string[];
  requirements_hard: string[];
  requirements_soft: string[];
  education_requirements: string[];
  certifications: string[];
  hard_requirements: string[];
  soft_requirements: string[];
  responsibilities: string[];
  tools_and_technologies: string[];
  domain_keywords: string[];
  soft_skills: string[];
  ats_keywords: string[];
  responsibility_clusters: Record<string, string[]>;
  weight_map: Record<string, number>;
  required_skills: string[];
  optional_skills: string[];
};

export type AnalysisResult = {
  id: number;
  resume_id: number;
  job_profile_id: number | null;
  status: "queued" | "processing" | "completed" | "failed";
  match_score: number | null;
  extracted_metadata: {
    skills: string[];
    skill_count: number;
    sections_detected: string[];
    section_count: number;
    experience_years: number;
    contact_info: {
      has_email: boolean;
      has_phone: boolean;
      has_linkedin: boolean;
    };
    word_count: number;
  } | null;
  job_match_result: JobMatchResult | null;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
};

export async function register(email: string, password: string) {
  const response = await fetch(`${API_BASE_URL}/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail || "Failed to register user");
  }

  return response.json();
}

export async function login(email: string, password: string): Promise<LoginResponse> {
  const response = await fetch(`${API_BASE_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail || "Failed to log in");
  }

  return response.json();
}

export async function createJobDescription(
  token: string,
  payload: { title: string; company: string; description_text: string }
) {
  const response = await fetch(`${API_BASE_URL}/job-descriptions`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error("Failed to create job description");
  }

  return response.json();
}

export async function uploadResume(token: string, file: File): Promise<Resume> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_BASE_URL}/resumes/upload`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
    },
    body: formData,
  });

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail || "Failed to upload resume");
  }

  return response.json();
}

export async function listResumes(token: string): Promise<Resume[]> {
  const response = await fetch(`${API_BASE_URL}/resumes`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    throw new Error("Failed to fetch resumes");
  }

  return response.json();
}

export async function getDashboardStats(token: string): Promise<DashboardStats> {
  const response = await fetch(`${API_BASE_URL}/dashboard/stats`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    throw new Error("Failed to fetch dashboard stats");
  }

  return response.json();
}

// ---------------------------------------------------------------------------
// Analysis API
// ---------------------------------------------------------------------------

export async function triggerAnalysis(
  token: string,
  resumeId: number
): Promise<AnalysisQueued> {
  const response = await fetch(`${API_BASE_URL}/analysis/run`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ resume_id: resumeId }),
  });

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail || "Failed to trigger analysis");
  }

  return response.json();
}

export async function getAnalysis(
  token: string,
  analysisId: number
): Promise<AnalysisResult> {
  const response = await fetch(`${API_BASE_URL}/analysis/${analysisId}`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail || "Failed to fetch analysis");
  }

  return response.json();
}

export async function getAnalysisByResume(
  token: string,
  resumeId: number
): Promise<AnalysisResult | null> {
  const response = await fetch(`${API_BASE_URL}/analysis/by-resume/${resumeId}`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (response.status === 404) {
    return null;
  }

  if (!response.ok) {
    throw new Error("Failed to fetch analysis");
  }

  return response.json();
}

export async function getAnalysisHistoryByResume(
  token: string,
  resumeId: number
): Promise<AnalysisResult[]> {
  const response = await fetch(`${API_BASE_URL}/analysis/by-resume/${resumeId}/history`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    throw new Error("Failed to fetch analysis history");
  }

  return response.json();
}

// ---------------------------------------------------------------------------
// Job Profile API
// ---------------------------------------------------------------------------

export async function listJobProfiles(token: string): Promise<JobProfile[]> {
  const response = await fetch(`${API_BASE_URL}/job-profiles/`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) throw new Error("Failed to fetch job profiles");
  return response.json();
}

export async function createJobProfile(
  token: string,
  payload: {
    title: string;
    raw_description?: string;
    seniority_level?: string;
    required_skills?: string[];
    optional_skills?: string[];
    responsibilities?: string[];
    years_experience_min?: number;
    years_experience_max?: number;
  }
): Promise<JobProfile> {
  const response = await fetch(`${API_BASE_URL}/job-profiles/`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail || "Failed to create job profile");
  }
  return response.json();
}

export async function parseJobProfilePreview(
  token: string,
  payload: { title: string; raw_description: string }
): Promise<JobTargetPreview> {
  const response = await fetch(`${API_BASE_URL}/job-profiles/parse-preview`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail || "Failed to parse job description");
  }
  return response.json();
}

export async function getJobProfile(
  token: string,
  profileId: number
): Promise<JobProfile> {
  const response = await fetch(`${API_BASE_URL}/job-profiles/${profileId}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) throw new Error("Failed to fetch job profile");
  return response.json();
}

export async function updateJobProfile(
  token: string,
  profileId: number,
  payload: Partial<{
    title: string;
    seniority_level: string;
    required_skills: string[];
    optional_skills: string[];
    responsibilities: string[];
    years_experience_min: number;
    years_experience_max: number;
  }>
): Promise<JobProfile> {
  const response = await fetch(`${API_BASE_URL}/job-profiles/${profileId}`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error("Failed to update job profile");
  return response.json();
}

export async function deleteJobProfile(
  token: string,
  profileId: number
): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/job-profiles/${profileId}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) throw new Error("Failed to delete job profile");
}

export async function getLastUsedProfile(
  token: string
): Promise<JobProfile | null> {
  const response = await fetch(`${API_BASE_URL}/job-profiles/last-used`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) throw new Error("Failed to fetch last used profile");
  const data = await response.json();
  return data || null;
}

export async function triggerTargetedAnalysis(
  token: string,
  resumeId: number,
  jobProfileId: number
): Promise<AnalysisQueued> {
  const response = await fetch(`${API_BASE_URL}/analysis/run-targeted`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ resume_id: resumeId, job_profile_id: jobProfileId }),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail || "Failed to trigger targeted analysis");
  }
  return response.json();
}
