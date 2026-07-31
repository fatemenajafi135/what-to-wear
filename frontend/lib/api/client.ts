import createOpenapiClient from "openapi-fetch";
import { createClient as createSupabaseClient } from "@/lib/supabase/client";
import type { paths } from "./schema";

/**
 * Thin `openapi-fetch` wrapper over the generated `paths` type
 * (schema.d.ts, regenerated via `npm run generate:api-types` whenever the
 * backend's routes change — never hand-edited, Constitution VII). Every
 * request carries the current Supabase session's access token, since every
 * closet route requires `get_current_user_id` (feature 003).
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
