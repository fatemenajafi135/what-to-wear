import { createClient } from "@supabase/supabase-js";

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

if (!supabaseUrl || !supabaseAnonKey) {
  throw new Error(
    "NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY are required (see .env.local.example)"
  );
}

// Default session persistence (localStorage) is what satisfies FR-002 --
// staying signed in across a reload/reopen -- with zero custom code.
export const supabase = createClient(supabaseUrl, supabaseAnonKey);
