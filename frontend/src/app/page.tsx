"use client";

import { FormEvent, useState } from "react";

import { createJobDescription, login, register } from "@/lib/api";

type ApiResult = Record<string, unknown> | null;

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
  const [error, setError] = useState("");

  const handleRegister = async (event: FormEvent) => {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      const data = await register(email, password);
      setResult(data);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const handleLogin = async (event: FormEvent) => {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      const data = await login(email, password);
      setToken(data.access_token);
      setResult(data);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateJd = async (event: FormEvent) => {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      const data = await createJobDescription(token, {
        title,
        company,
        description_text: descriptionText,
      });
      setResult(data);
    } catch (err) {
      setError((err as Error).message);
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
          <button type="submit" disabled={loading || !token}>
            Save JD
          </button>
        </form>
      </section>

      {error ? <p>{error}</p> : null}
      {result ? <pre>{JSON.stringify(result, null, 2)}</pre> : null}
    </main>
  );
}
