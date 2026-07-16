"use client";

import { useEffect, useState } from "react";
import { apiFetch, ApiError } from "@/lib/api-client";
import type { PreferenceProfile } from "@/lib/types";
import { PreferencesView } from "@/components/PreferencesView";

export default function PreferencesPage() {
  const [profile, setProfile] = useState<PreferenceProfile | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function load() {
    apiFetch<PreferenceProfile>("/preferences")
      .then(setProfile)
      .catch((err) => {
        setError(err instanceof ApiError ? `Couldn't load your preferences (${err.status}).` : "Couldn't load your preferences.");
      });
  }

  useEffect(() => {
    load();
  }, []);

  async function handleRemoveSignal(key: string) {
    setBusy(true);
    setError(null);
    try {
      await apiFetch(`/preferences/signals/${encodeURIComponent(key)}`, { method: "DELETE" });
      load();
    } catch (err) {
      setError(err instanceof ApiError ? `Couldn't remove that preference (${err.status}).` : "Couldn't remove that preference.");
    } finally {
      setBusy(false);
    }
  }

  async function handleClearAll() {
    setBusy(true);
    setError(null);
    try {
      await apiFetch("/preferences", { method: "DELETE" });
      load();
    } catch (err) {
      setError(err instanceof ApiError ? `Couldn't clear your preferences (${err.status}).` : "Couldn't clear your preferences.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="preferences-page">
      <h1>Your preferences</h1>
      <p className="text-muted">What we&apos;ve learned from the outfits you&apos;ve liked and rejected.</p>

      {error && <p className="page-error">{error}</p>}

      {profile === null && !error && <p className="text-muted">Loading…</p>}

      {profile !== null && (
        <PreferencesView profile={profile} onRemoveSignal={handleRemoveSignal} onClearAll={handleClearAll} busy={busy} />
      )}
    </div>
  );
}
