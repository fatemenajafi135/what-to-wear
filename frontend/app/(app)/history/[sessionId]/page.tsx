"use client";

import { use, useCallback, useEffect, useState } from "react";
import { TopHeader } from "@/components/ui/TopHeader/TopHeader";
import { Button } from "@/components/ui/Button/Button";
import { apiClient } from "@/lib/api/client";
import { useOnlineStatus } from "@/lib/useOnlineStatus";
import type { components } from "@/lib/api/schema";
import { HistoryList } from "../HistoryList";
import { formatSessionDate } from "../formatSessionDate";
import { SessionMessages } from "./SessionMessages";
import { SessionActions } from "./SessionActions";
import twoPaneStyles from "../page.module.css";
import styles from "./page.module.css";

type SessionDetailResponse = components["schemas"]["SessionDetailResponse"];

/**
 * `/history/:sessionId` — design/design-system.md § Chat history / Session
 * detail item 2: `TopHeader` (title "Conversation", subtitle = session
 * date, back arrow, no right slot), the full read-only thread, then —
 * below it — "Continue conversation" (always) and "{count} → View in
 * Outfits" (only when the session produced outfits). At ≥1024px the
 * Chat-history list renders in a pane to the left, mirroring
 * `/outfits/[outfitId]/page.tsx`'s own two-pane composition.
 */
export default function SessionDetailPage({ params }: { params: Promise<{ sessionId: string }> }) {
  const { sessionId } = use(params);
  const [session, setSession] = useState<SessionDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState(false);
  const isOnline = useOnlineStatus();

  const load = useCallback(async () => {
    setLoading(true);
    setNotFound(false);
    setError(false);
    try {
      const { data, response } = await apiClient.GET("/api/v1/recommend/sessions/{session_id}", {
        params: { path: { session_id: sessionId } },
      });
      if (response.status === 404) {
        setNotFound(true);
        return;
      }
      if (!data) {
        setError(true);
        return;
      }
      setSession(data);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  useEffect(() => {
    load();
  }, [load]);

  const showError = error && isOnline; // offline suppresses the screen's own error (design-system §6)

  return (
    <div className={twoPaneStyles.twoPane}>
      <div className={twoPaneStyles.gridPane}>
        <HistoryList selectedSessionId={sessionId} />
      </div>

      <div>
        <TopHeader
          title="Conversation"
          subtitle={session ? formatSessionDate(session.updated_at) : undefined}
          backHref="/history"
        />

        {loading && (
          // design-system.md § Per-screen skeleton layouts convention:
          // approximates two message bubbles.
          <div aria-hidden="true">
            <div className={`${styles.skeletonBar} skeleton`} />
          </div>
        )}

        {!loading && notFound && (
          <div className={styles.stateBlock}>
            <p className={`textBody ${styles.stateBody}`}>
              This conversation couldn&apos;t be found — it may have been removed.
            </p>
            <Button href="/history" width="intrinsic">
              Back to Chat history
            </Button>
          </div>
        )}

        {!loading && showError && (
          <div className={styles.stateBlock}>
            <p className={`textBody ${styles.stateBody}`}>Couldn&apos;t load your history.</p>
            <Button width="intrinsic" onClick={load}>
              Retry
            </Button>
          </div>
        )}

        {!loading && !notFound && !error && session && (
          <div className={styles.wrapper}>
            <SessionMessages messages={session.messages} />
            <SessionActions sessionId={session.id} outfitCount={session.outfit_count} />
          </div>
        )}
      </div>
    </div>
  );
}
