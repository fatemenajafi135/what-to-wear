import { supabase } from "./supabase-client";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL;

if (!API_BASE_URL) {
  throw new Error("NEXT_PUBLIC_API_BASE_URL is required (see .env.local.example)");
}

export class ApiError extends Error {
  status: number;
  body: unknown;

  constructor(status: number, body: unknown) {
    super(`API error ${status}`);
    this.status = status;
    this.body = body;
  }
}

const REDIRECT_TARGET_KEY = "wtw:redirect-after-signin";

/** Thin fetch wrapper: attaches the signed-in user's JWT, applies the
 * caller-supplied init as-is (JSON body + Content-Type, or a FormData body
 * with no Content-Type so the browser sets its own multipart boundary).
 * Does NOT redirect on 401 itself -- see redirectToSignIn below, which
 * callers use explicitly so in-progress form state isn't silently
 * discarded (spec Edge Cases: "session expires mid-action"). */
export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const {
    data: { session },
  } = await supabase.auth.getSession();

  const headers = new Headers(init.headers);
  if (session?.access_token) {
    headers.set("Authorization", `Bearer ${session.access_token}`);
  }

  const res = await fetch(`${API_BASE_URL}${path}`, { ...init, headers });

  if (!res.ok) {
    let body: unknown = null;
    try {
      body = await res.json();
    } catch {
      // non-JSON error body -- leave body null, status is still informative
    }
    throw new ApiError(res.status, body);
  }

  if (res.status === 204) {
    return undefined as T;
  }
  return (await res.json()) as T;
}

/** Call from a catch block on ApiError(401): stashes an optional in-progress
 * draft plus the current path, then navigates to /sign-in. The page that
 * lost its draft is responsible for checking restoreDraft() on remount and
 * for reading popRedirectTarget() isn't needed there -- the sign-in page
 * itself reads popRedirectTarget() after a successful sign-in. */
export function redirectToSignIn(draftKey?: string, draft?: unknown): void {
  if (draftKey && draft !== undefined) {
    sessionStorage.setItem(draftKey, JSON.stringify(draft));
  }
  sessionStorage.setItem(REDIRECT_TARGET_KEY, window.location.pathname);
  window.location.href = "/sign-in";
}

export function restoreDraft<T>(draftKey: string): T | null {
  const raw = sessionStorage.getItem(draftKey);
  if (raw === null) return null;
  sessionStorage.removeItem(draftKey);
  try {
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}

/** Read (and clear) the path to return to after a successful sign-in --
 * set by redirectToSignIn when a session expired mid-action. */
export function popRedirectTarget(): string | null {
  const target = sessionStorage.getItem(REDIRECT_TARGET_KEY);
  if (target !== null) sessionStorage.removeItem(REDIRECT_TARGET_KEY);
  return target;
}

export interface SSEEvent {
  event: string;
  data: string;
}

/** Streams a POST endpoint's Server-Sent Events (contracts/suggest.md).
 * A new function alongside apiFetch, not a modification to it -- every
 * other endpoint depends on apiFetch staying a simple request/response
 * call. Browsers' native EventSource only supports GET, and /suggest is
 * POST, so this hand-rolls the `event:`/`data:` framing over fetch()'s
 * streaming response body instead (T036a). Yields each event as it
 * arrives; the caller JSON.parses `data` itself since its shape differs
 * per event name (`outfit` vs `done`). */
export async function* postSSE(path: string, body: unknown): AsyncGenerator<SSEEvent> {
  const {
    data: { session },
  } = await supabase.auth.getSession();

  const headers = new Headers({ "Content-Type": "application/json" });
  if (session?.access_token) {
    headers.set("Authorization", `Bearer ${session.access_token}`);
  }

  const res = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    let errorBody: unknown = null;
    try {
      errorBody = await res.json();
    } catch {
      // non-JSON error body -- leave errorBody null, status is still informative
    }
    throw new ApiError(res.status, errorBody);
  }
  if (!res.body) {
    throw new Error("streaming response has no body");
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let separatorIndex: number;
    while ((separatorIndex = buffer.indexOf("\n\n")) !== -1) {
      const block = buffer.slice(0, separatorIndex);
      buffer = buffer.slice(separatorIndex + 2);

      const eventLine = block.split("\n").find((line) => line.startsWith("event: "));
      const dataLine = block.split("\n").find((line) => line.startsWith("data: "));
      if (dataLine) {
        yield { event: eventLine?.slice("event: ".length) ?? "message", data: dataLine.slice("data: ".length) };
      }
    }
  }
}
