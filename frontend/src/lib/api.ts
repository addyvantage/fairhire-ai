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
};

export type AnalysisQueued = {
  analysis_id: number;
  status: string;
  created_at: string;
};

export type AnalysisResult = {
  id: number;
  resume_id: number;
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
