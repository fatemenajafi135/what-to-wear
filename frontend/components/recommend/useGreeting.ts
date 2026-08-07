"use client";

import { useEffect, useState } from "react";
import { createClient } from "@/lib/supabase/client";
import { greetingFor, nameFromEmail } from "@/lib/recommend/timeOfDayGreeting";

/**
 * "{greeting}, {name}" per design-system.md §9/Screen anatomy → Recommend.
 * `{name}` is derived from the session email (docs/design-decisions.md §29
 * — no display-name field exists anywhere in this app). Computed once on
 * mount from the device's local time, same as `app/(app)/profile/page.tsx`'s
 * existing `supabase.auth.getSession()` pattern.
 */
export function useGreeting(): string {
  const [greeting, setGreeting] = useState(() => greetingFor(new Date().getHours()));
  const [name, setName] = useState("there");

  useEffect(() => {
    setGreeting(greetingFor(new Date().getHours()));
    const supabase = createClient();
    supabase.auth.getSession().then(({ data }) => {
      setName(nameFromEmail(data.session?.user.email));
    });
  }, []);

  return `${greeting}, ${name}`;
}
