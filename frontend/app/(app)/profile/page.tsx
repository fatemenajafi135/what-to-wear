"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { IconButton } from "@/components/ui/IconButton/IconButton";
import { Button } from "@/components/ui/Button/Button";
import { createClient } from "@/lib/supabase/client";
import { signOutAndClearCache } from "@/lib/auth/signOut";
import { getProfile, type ProfileResponse } from "@/lib/api/profile";
import { useOnlineStatus } from "@/lib/useOnlineStatus";
import styles from "./page.module.css";

type LoadState = "loading" | "ready" | "error";

const BODY_SHAPE_LABELS: Record<string, string> = {
  hourglass: "Hourglass",
  pear: "Pear",
  rectangle: "Rectangle",
  apple: "Apple",
  inverted_triangle: "Inverted triangle",
};

const GENDER_LABELS: Record<string, string> = {
  woman: "Woman",
  man: "Man",
  non_binary: "Non-binary",
  prefer_not_to_say: "Prefer not to say",
};

/**
 * design/design-system.md §8: Profile has no TopHeader, so its <h1> is
 * visually hidden. Three <h2>-headed summary cards — Account, Style
 * preferences, Body & size — per specs/013-profile-settings/research.md §4
 * (design-system.md names "three cards" but never their contents; this is
 * the recorded decision).
 */
export default function ProfilePage() {
  const router = useRouter();
  const [state, setState] = useState<LoadState>("loading");
  const [profile, setProfile] = useState<ProfileResponse | null>(null);
  const [email, setEmail] = useState<string | null>(null);
  const isOnline = useOnlineStatus();
  const isOffline = !isOnline;

  async function load() {
    setState("loading");
    try {
      const supabase = createClient();
      const [profileResult, sessionResult] = await Promise.all([
        getProfile(),
        supabase.auth.getSession(),
      ]);
      setProfile(profileResult);
      setEmail(sessionResult.data.session?.user.email ?? null);
      setState("ready");
    } catch {
      setState("error");
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function handleSignOut() {
    const supabase = createClient();
    await signOutAndClearCache(supabase);
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

      {state === "loading" && (
        <div className={styles.cards}>
          <div className={`skeleton ${styles.skeletonCard}`} />
          <div className={`skeleton ${styles.skeletonCard}`} />
          <div className={`skeleton ${styles.skeletonCard}`} />
        </div>
      )}

      {state === "error" && !isOffline && (
        <div className={styles.errorBanner}>
          <p className="textBody">That didn&apos;t save. Check your connection and try again.</p>
          <Button variant="outline" width="intrinsic" onClick={load}>
            Retry
          </Button>
        </div>
      )}

      {state === "ready" && profile && (
        <div className={styles.cards}>
          <section className={styles.card}>
            <h2 className="textSectionTitle">Account</h2>
            <p className={`textLabel ${styles.fieldLabel}`}>Email</p>
            <p className="textBody">{email ?? "—"}</p>
          </section>

          <section className={styles.card}>
            <h2 className="textSectionTitle">Style preferences</h2>
            <p className={`textLabel ${styles.fieldLabel}`}>Fit &amp; style</p>
            <p className="textBody">
              {profile.style_tags && profile.style_tags.length > 0
                ? profile.style_tags.join(", ")
                : "Not set yet"}
            </p>
            <p className={`textLabel ${styles.fieldLabel}`}>Colour palettes</p>
            <p className="textBody">
              {profile.colour_tags && profile.colour_tags.length > 0
                ? profile.colour_tags.join(", ")
                : "Not set yet"}
            </p>
          </section>

          <section className={styles.card}>
            <h2 className="textSectionTitle">Body &amp; size</h2>
            {profile.body_shape && (
              <>
                <p className={`textLabel ${styles.fieldLabel}`}>Body shape</p>
                <p className="textBody">{BODY_SHAPE_LABELS[profile.body_shape]}</p>
              </>
            )}
            {profile.gender && (
              <>
                <p className={`textLabel ${styles.fieldLabel}`}>Gender</p>
                <p className="textBody">{GENDER_LABELS[profile.gender]}</p>
              </>
            )}
            {profile.height && (
              <>
                <p className={`textLabel ${styles.fieldLabel}`}>Height</p>
                <p className="textBody">{profile.height}</p>
              </>
            )}
            {!profile.body_shape && !profile.gender && !profile.height && (
              <p className="textBody">Not set yet</p>
            )}
          </section>
        </div>
      )}

      <div className={styles.signOut}>
        <Button variant="outline" width="intrinsic" onClick={handleSignOut}>
          Sign out
        </Button>
      </div>
    </>
  );
}
