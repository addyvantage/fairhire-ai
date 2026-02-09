"use client";

import { FormEvent, useEffect, useState } from "react";

import { createJobDescription, login, register } from "@/lib/api";

type ApiResult = Record<string, unknown> | null;

const TOKEN_KEY = "fairhire_access_token";

export default function HomePage() {
  const [email, setEmail] = useState("founder@fairhire.ai");
  const [password, setPassword] = useState("ChangeMe123!");
  const [token, setToken] = useState("");

  const [title, setTitle] = useState("Machine Learning Engineer");
  const [company, setCompany] = useState("FairHire Labs");
  const [descriptionText, setDescriptionText] = useState(
    "We are seeking a Python engineer with experience in FastAPI, SQL, and cloud systems."
  );

  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ApiResult>(null);
  const [authError, setAuthError] = useState("");
  const [jdError, setJdError] = useState("");

  // Rehydrate token from localStorage on mount
  useEffect(() => {
    const stored = localStorage.getItem(TOKEN_KEY);
    if (stored) {
      setToken(stored);
    }
  }, []);

  const handleRegister = async (event: FormEvent) => {
    event.preventDefault();
    setLoading(true);
    setAuthError("");
    try {
      const data = await register(email, password);
      setResult(data);
    } catch (err) {
      const msg = (err as Error).message;
      console.error("Register failed:", err);
      setAuthError(msg);
    } finally {
      setLoading(false);
    }
  };

  const handleLogin = async (event: FormEvent) => {
    event.preventDefault();
    setLoading(true);
    setAuthError("");
    try {
      const data = await login(email, password);
      setToken(data.access_token);
      localStorage.setItem(TOKEN_KEY, data.access_token);
      setResult(data);
    } catch (err) {
      const msg = (err as Error).message;
      console.error("Login failed:", err);
      setAuthError(msg);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateJd = async (event: FormEvent) => {
    event.preventDefault();
    if (!token) {
      setJdError("Not authenticated. Please log in first.");
      return;
    }
    setLoading(true);
    setJdError("");
    try {
      const data = await createJobDescription(token, {
        title,
        company,
        description_text: descriptionText,
      });
      setResult(data);
    } catch (err) {
      const msg = (err as Error).message;
      console.error("Create JD failed:", err);
      setJdError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <main>
      <h1>FairHire-AI</h1>
      <p>Phase 1 frontend scaffold for API contract validation.</p>

      <section>
        <h2>Register</h2>
        <form onSubmit={handleRegister}>
          <input
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            type="email"
            placeholder="Email"
          />
          <input
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            type="password"
            placeholder="Password"
          />
          <button type="submit" disabled={loading}>
            Create Account
          </button>
        </form>
      </section>

      <section>
        <h2>Login</h2>
        <form onSubmit={handleLogin}>
          <input
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            type="email"
            placeholder="Email"
          />
          <input
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            type="password"
            placeholder="Password"
          />
          <button type="submit" disabled={loading}>
            Login
          </button>
        </form>
        {token ? <p>Token acquired.</p> : null}
        {authError ? <p style={{ color: "red" }}>{authError}</p> : null}
      </section>

      <section>
        <h2>Create Job Description</h2>
        <form onSubmit={handleCreateJd}>
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Role title"
          />
          <input
            value={company}
            onChange={(e) => setCompany(e.target.value)}
            placeholder="Company"
          />
          <textarea
            value={descriptionText}
            onChange={(e) => setDescriptionText(e.target.value)}
            rows={5}
          />
          <button type="submit" disabled={loading}>
            Save JD
          </button>
        </form>
        {!token && !jdError ? (
          <p style={{ color: "orange" }}>Log in before saving a job description.</p>
        ) : null}
        {jdError ? <p style={{ color: "red" }}>{jdError}</p> : null}
      </section>

      {result ? <pre>{JSON.stringify(result, null, 2)}</pre> : null}
    </main>
  );
}
