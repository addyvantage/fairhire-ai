const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export type LoginResponse = {
  access_token: string;
  token_type: string;
};

export type Resume = {
  id: string;
  filename: string;
  status: "pending" | "processing" | "completed" | "failed";
  uploaded_at: string;
  match_score?: number;
};

export type DashboardStats = {
  total_resumes: number;
  analyses_run: number;
  avg_match_score: number;
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
