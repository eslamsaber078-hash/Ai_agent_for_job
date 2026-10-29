import { setTask, taskStep, track, watchSlowness } from "./progress";
import { translate } from "./translations";

// Trailing slashes are stripped so VITE_API_URL=/ (production, same-origin)
// joins into /api/... instead of the protocol-relative //api/... .
const BASE = (import.meta.env.VITE_API_URL ?? `${window.location.protocol}//${window.location.hostname}:8000`).replace(/\/+$/, "");

export const AUTH_EXPIRED_EVENT = "auth-expired";

/** AI answers (a CV, a cover letter) are two provider calls after a cold model; a
 *  minute is normal, so the ordinary request timeout must not cut them off. */
export const AI_TIMEOUT = 120_000;

/**
 * A line the server (or this client) wrote, in the language the screen is using.
 *
 * Every message that ends up in a toast passes through here. The dictionary keys on the
 * English text, so a line it knows comes back translated and one it does not — a scraped
 * error, a validation string — comes back exactly as it was written. Without this, an
 * Arabic screen answers a failed press in English.
 */
export function localize(message: string): string {
  const stage = /^This application is already at (.+)$/.exec(message);
  if (stage) return translate("This application is already at {stage}", { stage: translate(stage[1]) });
  return translate(message);
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(localize(message));
    this.status = status;
  }
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

// The host is a free instance that stops itself after a quiet spell, so the first
// visit of the day spends up to a minute booting. A request has to be allowed to
// wait that long, but a request during normal use that takes this long is a fault.
const ATTEMPT_TIMEOUT = 15_000;
const WAKE_TIMEOUT = 75_000;
const QUIET_BEFORE_WAKE = 45_000;
// 502/503/504 are what a proxy says while the process behind it is booting or busy.
const TRANSIENT = new Set([502, 503, 504]);

let lastAnsweredAt = 0;

function attemptTimeout(): number {
  return Date.now() - lastAnsweredAt > QUIET_BEFORE_WAKE ? WAKE_TIMEOUT : ATTEMPT_TIMEOUT;
}

function retryDelay(attempt: number, res?: Response): number {
  const after = Number(res?.headers.get("Retry-After"));
  if (Number.isFinite(after) && after > 0) return Math.min(after * 1000, 8000);
  return Math.min(600 * 2 ** (attempt - 1), 5000) + Math.random() * 250;
}

async function fetchJson(path: string, options: RequestInit, retries: number, timeout?: number): Promise<Response> {
  const headers = new Headers(options.headers);
  if (!(options.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (!["GET", "HEAD", "OPTIONS"].includes((options.method ?? "GET").toUpperCase())) {
    headers.set("X-Requested-With", "XMLHttpRequest");
  }
  let attempt = 0;
  for (;;) {
    // Without this a dropped socket leaves the spinner turning forever: the browser
    // keeps the request open long past the point where anyone is still serving it.
    const controller = new AbortController();
    let timedOut = false;
    const timer = window.setTimeout(() => {
      timedOut = true;
      controller.abort();
    }, timeout ?? attemptTimeout());
    let res: Response | null = null;
    try {
      res = await fetch(`${BASE}${path}`, { ...options, headers, credentials: "include", signal: controller.signal });
      // Only an answer the server actually produced counts as "awake". A 502 from the
      // proxy while it boots must not reset the clock, or the retry would fall back to
      // the short timeout and give up on a boot that is still in progress.
      if (res.status < 500) lastAnsweredAt = Date.now();
    } catch {
      /* offline, DNS, or our own timeout — all worth one more try */
    } finally {
      window.clearTimeout(timer);
    }
    const retryable = res === null || TRANSIENT.has(res.status);
    if (!retryable || attempt >= retries) {
      const endpoint = path.split(/[?#]/)[0].replace(/\/$/, "");
      if (res?.status === 401 && !endpoint.startsWith("/api/auth/") && endpoint !== "/api/health") {
        window.dispatchEvent(new Event(AUTH_EXPIRED_EVENT));
      }
      if (res) return res;
      throw new ApiError(0, timedOut
        ? "The server took too long to answer. Check your connection and try again."
        : "Cannot reach the server. Check your connection and try again.");
    }
    // Release the socket we are walking away from; a burst of proxy 502s would
    // otherwise hold a connection each until the browser times them out.
    void res?.body?.cancel();
    attempt += 1;
    await sleep(retryDelay(attempt, res ?? undefined));
  }
}

const STATUS_FALLBACK: Record<number, string> = {
  502: "The server is starting up — try again in a moment.",
  503: "The server is busy — try again in a moment.",
  504: "The server is starting up — try again in a moment.",
};

async function readError(res: Response): Promise<ApiError> {
  let detail = STATUS_FALLBACK[res.status] ?? `Request failed (${res.status})`;
  try {
    const body = await res.json();
    if (typeof body.detail === "string") detail = body.detail;
    else if (Array.isArray(body.detail)) detail = body.detail.map((d: any) => d.msg).join("; ");
  } catch {
    /* keep default — a proxy's HTML error page is not a message for him */
  }
  return new ApiError(res.status, detail);
}

interface RequestOptions {
  /** Progress-bar tracking. Disable for background polls like the health check. */
  track?: boolean;
  /** Connection retries for read-only GETs (default 2). */
  retries?: number;
  /** Response timeout. Only AI generation sets this: it can legitimately run for a
   *  minute, and the ordinary 15s ceiling would abort it mid-answer. */
  timeout?: number;
}

async function request<T>(path: string, options: RequestInit = {}, opts: RequestOptions = {}): Promise<T> {
  const { track: tracked = true, retries, timeout } = opts;
  const isGet = !options.method || options.method === "GET";
  const attempts = retries ?? (isGet ? 2 : 0);
  const call = async () => {
    // A call that is allowed to take a minute has its own honest spinner; labelling
    // it "waking the server" would tell him the wrong story.
    const done = timeout ? () => {} : watchSlowness();
    try {
      let res: Response;
      try {
        res = await fetchJson(path, options, attempts, timeout);
      } catch (err) {
        if (err instanceof ApiError) throw err;
        throw new ApiError(0, "Cannot reach the server. Check your connection and try again.");
      }
      if (!res.ok) throw await readError(res);
      return (await res.json()) as T;
    } finally {
      done();
    }
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
          throw new ApiError(0, "Cannot reach the server. Check your connection and try again.");
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
