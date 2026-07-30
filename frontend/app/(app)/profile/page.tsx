"use client";

import { useRouter } from "next/navigation";
import { IconButton } from "@/components/ui/IconButton/IconButton";
import { Button } from "@/components/ui/Button/Button";
import { createClient } from "@/lib/supabase/client";
import styles from "./page.module.css";

/**
 * Stub route — chrome + empty placeholder, plus sign-out (spec.md FR-013 —
 * the one control this slice's Profile actually needs; the rest is
 * deferred per known-gaps.md §0.6). Profile has no visible "Profile"
 * title text in the real design (per design/design-system.md §8), so the
 * screen's <h1> is visually hidden but still focusable for FR-009's
 * focus-on-navigate requirement.
 */
export default function ProfilePage() {
  const router = useRouter();

  async function handleSignOut() {
    const supabase = createClient();
    await supabase.auth.signOut();
    router.push("/signin");
    router.refresh();
  }

  return (
    <>
      <div className={styles.header}>
        <h1 className="visuallyHidden" tabIndex={-1}>
          Profile
        </h1>
        <IconButton icon="settings" href="/profile/settings" />
      </div>
      <div className={styles.empty}>
        <p className={`textBody ${styles.body}`}>
          Profile details aren&apos;t wired up yet in this slice — this screen
          shows its chrome only.
        </p>
        <Button variant="outline" width="intrinsic" onClick={handleSignOut}>
          Sign out
        </Button>
      </div>
    </>
  );
}
