const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public code?: string,
  ) {
    super(message);
  }
}

const TOKEN_KEY = "cp_token";

export const tokenStore = {
  get: () => (typeof window === "undefined" ? null : window.localStorage.getItem(TOKEN_KEY)),
  set: (t: string) => window.localStorage.setItem(TOKEN_KEY, t),
  clear: () => window.localStorage.removeItem(TOKEN_KEY),
};

type Options = Omit<RequestInit, "body"> & { body?: unknown; token?: string | null; query?: Record<string, string | number | boolean | undefined | null> };

/** Thin typed fetch wrapper. Response types come from the schema generated from FastAPI (src/lib/api-schema.d.ts). */
export async function api<T>(path: string, { body, token, query, headers, ...init }: Options = {}): Promise<T> {
  const qs = query
    ? "?" +
      new URLSearchParams(
        Object.entries(query)
          .filter(([, v]) => v !== undefined && v !== null && v !== "")
          .map(([k, v]) => [k, String(v)]),
      ).toString()
    : "";
  const auth = token === undefined ? tokenStore.get() : token;
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}${qs}`, {
      ...init,
      headers: {
        ...(body !== undefined && !(body instanceof FormData) ? { "Content-Type": "application/json" } : {}),
        ...(auth ? { Authorization: `Bearer ${auth}` } : {}),
        ...headers,
      },
      body: body === undefined ? undefined : body instanceof FormData ? body : JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, "You appear to be offline. Check your connection and try again.", "offline");
  }
  if (res.status === 204) return undefined as T;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = (data as { detail?: unknown }).detail;
    const message = typeof detail === "string" ? detail : "Request failed";
    throw new ApiError(res.status, message, (data as { code?: string }).code);
  }
  return data as T;
}
