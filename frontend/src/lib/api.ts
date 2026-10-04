import type {
  AnalyzeResponse,
  ConfirmResponse,
  DatasetListResponse,
  DemoSeedResult,
  QueryResponse,
  User,
} from "./types";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
const TOKEN_KEY = "auth_token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(
  path: string,
  options: RequestInit & { asForm?: boolean } = {}
): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = { ...(options.headers as Record<string, string>) };
  if (!options.asForm) {
    headers["Content-Type"] = "application/json";
  }
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
      // ignore non-JSON error bodies
    }
    if (res.status === 401) {
      clearToken();
    }
    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  authGoogle: (idToken: string) =>
    request<{ token: string; user: User }>("/api/auth/google", {
      method: "POST",
      body: JSON.stringify({ id_token: idToken }),
    }),

  authDemo: (demoId: string) =>
    request<{ token: string; user: User }>("/api/auth/demo", {
      method: "POST",
      body: JSON.stringify({ demo_id: demoId }),
    }),

  me: () => request<User>("/api/auth/me"),

  listDatasets: () => request<DatasetListResponse>("/api/datasets"),

  uploadDataset: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<{ id: string; name: string; row_count: number; status: string }>(
      "/api/datasets/upload",
      { method: "POST", body: form, asForm: true }
    );
  },

  seedDemo: () =>
    request<{ results: DemoSeedResult[]; agent_log: string[] }>("/api/datasets/seed-demo", {
      method: "POST",
    }),

  analyzeDataset: (id: string) =>
    request<AnalyzeResponse>(`/api/datasets/${id}/analyze`, { method: "POST" }),

  confirmDataset: (
    id: string,
    body: { domains: { domain_id: string; columns: unknown[] }[] }
  ) =>
    request<ConfirmResponse>(`/api/datasets/${id}/confirm`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  datasetStatus: (id: string) =>
    request<{ id: string; status: string; error_message: string; row_count: number }>(
      `/api/datasets/${id}/status`
    ),

  deleteDataset: (id: string) => request<{ deleted: boolean }>(`/api/datasets/${id}`, { method: "DELETE" }),

  ask: (question: string, sessionId: string | null, persona?: string | null) =>
    request<QueryResponse>("/api/query", {
      method: "POST",
      body: JSON.stringify({ question, session_id: sessionId, persona: persona || null }),
    }),
};
