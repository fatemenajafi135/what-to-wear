import createOpenapiClient from "openapi-fetch";
import { createClient as createSupabaseClient } from "@/lib/supabase/client";
import type { paths } from "./schema";

/**
 * Thin `openapi-fetch` wrapper over the generated `paths` type (schema.d.ts,
 * regenerated via `npm run generate:api-types` whenever the backend's routes
 * change — never hand-edited, Constitution VII). Every request carries the
 * current Supabase session's access token, since every closet and profile
 * route requires `get_current_user_id` (feature 003).
 *
 * One client, shared by features 004 (closet) and 013 (profile/settings) —
 * see docs/design-decisions.md §20 for why this shape won over 013's
 * original hand-written `apiFetch` wrapper.
 */
export const apiClient = createOpenapiClient<paths>({
  baseUrl: process.env.NEXT_PUBLIC_API_URL,
});

apiClient.use({
  async onRequest({ request }) {
    const supabase = createSupabaseClient();
    const {
      data: { session },
    } = await supabase.auth.getSession();
    if (session?.access_token) {
      request.headers.set("Authorization", `Bearer ${session.access_token}`);
    }
    return request;
  },
});

/**
 * `openapi-fetch` never throws on a non-2xx response — every call site gets
 * back `{ data, error, response }` (see ClosetGrid.tsx's own destructuring).
 * `ApiError`/`unwrap` are feature 013's original typed-failure-handling
 * composed onto that shape, for call sites that prefer throw/catch
 * (Settings' Edit/Done sections): `unwrap` throws `ApiError` carrying the
 * real HTTP status when the request failed, otherwise returns `data`.
 */
export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

export function unwrap<T>(result: { data?: T; error?: unknown; response: Response }): T {
  if (result.error !== undefined || result.data === undefined) {
    throw new ApiError("Request failed", result.response.status);
  }
  return result.data;
}
