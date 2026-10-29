import { useSyncExternalStore } from "react";

/** One shared loading state for the whole app: every tracked request and every
 *  multi-step import reports here, and the top bar renders one coherent number. */
export interface ProgressState {
  /** How many tracked requests are in flight right now. */
  pending: number;
  /** Multi-step import currently running (site x of N), if any. */
  task: { done: number; total: number; label: string } | null;
  /** EMA of recent request durations in ms — lets the idle bar pace itself honestly. */
  avgMs: number;
  /** A request has been waiting long enough that the host is probably waking up. */
  slow: boolean;
}

let state: ProgressState = { pending: 0, task: null, avgMs: 400, slow: false };
const listeners = new Set<() => void>();

const DURATIONS: number[] = [];

export function beginRequest(): void {
  state = { ...state, pending: state.pending + 1 };
  for (const l of listeners) l();
}

export function endRequest(ms: number): void {
  // Clamp so one long stream (an import) can't poison the pacing of ordinary requests.
  DURATIONS.push(Math.min(ms, 8000));
  while (DURATIONS.length > 20) DURATIONS.shift();
  const ema = DURATIONS.reduce((a, b) => a + b, 0) / DURATIONS.length;
  state = { ...state, pending: Math.max(0, state.pending - 1), avgMs: Math.round(ema || 400) };
  for (const l of listeners) l();
}

export function setTask(task: ProgressState["task"]): void {
  state = { ...state, task };
  for (const l of listeners) l();
}

export function taskStep(label?: string): void {
  if (!state.task) return;
  state = { ...state, task: { ...state.task, done: state.task.done + 1, label: label ?? state.task.label } };
  for (const l of listeners) l();
}

function subscribe(fn: () => void): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

let slowCount = 0;

function shiftSlow(delta: number): void {
  slowCount = Math.max(0, slowCount + delta);
  state = { ...state, slow: slowCount > 0 };
  for (const l of listeners) l();
}

/** Watch one request for the length that means "the free host is waking", so the
 *  screen can say that instead of looking frozen. Call the returned function when
 *  the request settles, whatever happened to it. */
export function watchSlowness(afterMs = 4000): () => void {
  let counting = false;
  const timer = window.setTimeout(() => {
    counting = true;
    shiftSlow(1);
  }, afterMs);
  return () => {
    window.clearTimeout(timer);
    if (counting) shiftSlow(-1);
  };
}

const getSnapshot = () => state;

export function useProgress(): ProgressState {
  return useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
}

export function track<T>(promise: Promise<T>): Promise<T> {
  const start = performance.now();
  beginRequest();
  promise.finally(() => endRequest(performance.now() - start)).catch(() => {});
  return promise;
}
