import { setTask, taskStep, track } from "./progress";

// Trailing slashes are stripped so VITE_API_URL=/ (production, same-origin)
// joins into /api/... instead of the protocol-relative //api/... .
const BASE = (import.meta.env.VITE_API_URL ?? `${window.location.protocol}//${window.location.hostname}:8000`).replace(/\/+$/, "");

export const AUTH_EXPIRED_EVENT = "auth-expired";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

async function fetchJson(path: string, options: RequestInit, retries: number): Promise<Response> {
  const headers = new Headers(options.headers);
  if (!(options.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (!["GET", "HEAD", "OPTIONS"].includes((options.method ?? "GET").toUpperCase())) {
    headers.set("X-Requested-With", "XMLHttpRequest");
  }
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, { ...options, headers, credentials: "include" });
  } catch {
    if (retries > 0) {
      await sleep(1200);
      return fetchJson(path, options, retries - 1);
    }
    throw new ApiError(0, "Cannot reach the backend. Is it running on port 8000?");
  }
  const endpoint = path.split(/[?#]/)[0].replace(/\/$/, "");
  if (res.status === 401 && !endpoint.startsWith("/api/auth/") && endpoint !== "/api/health") {
    window.dispatchEvent(new Event(AUTH_EXPIRED_EVENT));
  }
  return res;
}

async function readError(res: Response): Promise<ApiError> {
  let detail = `Request failed (${res.status})`;
  try {
    const body = await res.json();
    if (typeof body.detail === "string") detail = body.detail;
    else if (Array.isArray(body.detail)) detail = body.detail.map((d: any) => d.msg).join("; ");
  } catch {
    /* keep default */
  }
  return new ApiError(res.status, detail);
}

interface RequestOptions {
  /** Progress-bar tracking. Disable for background polls like the health check. */
  track?: boolean;
  /** Connection retries for read-only GETs (default 2). */
  retries?: number;
}

async function request<T>(path: string, options: RequestInit = {}, opts: RequestOptions = {}): Promise<T> {
  const { track: tracked = true, retries } = opts;
  const isGet = !options.method || options.method === "GET";
  const attempts = retries ?? (isGet ? 2 : 0);
  const call = async () => {
    let res: Response;
    try {
      res = await fetchJson(path, options, attempts);
    } catch (err) {
      if (err instanceof ApiError) throw err;
      throw new ApiError(0, "Cannot reach the backend. Is it running on port 8000?");
    }
    if (!res.ok) throw await readError(res);
    return (await res.json()) as T;
  };
  return tracked ? track(call()) : call();
}

export interface StreamEvent {
  type: "progress" | "done" | "error";
  done?: number;
  total?: number;
  name?: string;
  label?: string;
  line?: string;
  jobs_new?: number;
  log?: string;
  status?: string;
  message?: string;
  run_id?: number;
  jobs_found?: number;
}

/** POST to an SSE endpoint: `onEvent` fires for every progress event, the shared top
 *  bar follows the same real percentage, and the promise resolves with the final
 *  `done` payload (or rejects with the `error` one). */
export async function postStream(
  path: string,
  body: unknown,
  onEvent: (ev: StreamEvent) => void
): Promise<StreamEvent> {
  return track(
    (async () => {
      let taskStarted = false;
      try {
        const res = await fetchJson(path, {
          method: "POST",
          headers: { Accept: "text/event-stream" },
          body: body === undefined ? undefined : JSON.stringify(body),
        }, 0);
        if (!res.ok) throw await readError(res);
        if (!res.body) throw new ApiError(0, "The backend sent no stream for this request.");
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        for (;;) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          let sep: number;
          while ((sep = buffer.indexOf("\n\n")) !== -1) {
            const chunk = buffer.slice(0, sep);
            buffer = buffer.slice(sep + 2);
            const data = chunk
              .split("\n")
              .filter((l) => l.startsWith("data: "))
              .map((l) => l.slice(6))
              .join("\n");
            if (!data.trim()) continue;
            let ev: StreamEvent;
            try {
              ev = JSON.parse(data) as StreamEvent;
            } catch {
              continue;
            }
            if (ev.type === "error") throw new ApiError(500, ev.message || "The import failed.");
            if (ev.type === "done") return ev;
            if (ev.type === "progress") {
              if (!taskStarted && ev.total) {
                setTask({ done: ev.done ?? 0, total: ev.total, label: ev.label ?? "" });
                taskStarted = true;
              } else if (taskStarted) {
                taskStep(ev.label);
              }
            }
            onEvent(ev);
          }
        }
        throw new ApiError(0, "The stream ended before the import finished.");
      } finally {
        if (taskStarted) setTask(null);
      }
    })()
  );
}

export const api = {
  get: <T>(path: string, opts: RequestOptions = {}) => request<T>(path, {}, opts),
  post: <T>(path: string, body?: unknown, opts: RequestOptions = {}) =>
    request<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) }, opts),
  put: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "PUT", body: body === undefined ? undefined : JSON.stringify(body) }),
  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "PATCH", body: body === undefined ? undefined : JSON.stringify(body) }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
  upload: async <T>(path: string, file: File): Promise<T> => {
    const form = new FormData();
    form.append("file", file);
    return track(
      (async () => {
        let res: Response;
        try {
          res = await fetchJson(path, { method: "POST", body: form }, 0);
        } catch (err) {
          if (err instanceof ApiError) throw err;
          throw new ApiError(0, "Cannot reach the backend. Is it running on port 8000?");
        }
        if (!res.ok) throw await readError(res);
        return (await res.json()) as T;
      })()
    );
  },
  downloadPdf: async (path: string): Promise<Blob> => {
    const res = await fetchJson(path, {}, 2);
    if (!res.ok) throw await readError(res);
    return res.blob();
  },
  postStream,
};

export function qs(params: Record<string, string | number | boolean | undefined | null>): string {
  const parts = Object.entries(params)
    .filter(([, v]) => v !== undefined && v !== null && v !== "")
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`);
  return parts.length ? `?${parts.join("&")}` : "";
}
