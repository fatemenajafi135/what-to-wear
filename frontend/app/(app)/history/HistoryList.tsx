"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/Button/Button";
import { apiClient } from "@/lib/api/client";
import { useOnlineStatus } from "@/lib/useOnlineStatus";
import type { components } from "@/lib/api/schema";
import { formatSessionDate } from "./formatSessionDate";
import styles from "./HistoryList.module.css";

type SessionSummary = components["schemas"]["SessionSummary"];

interface HistoryListProps {
  /** Highlights the currently-open session's row in the desktop two-pane layout. */
  selectedSessionId?: string;
}

/**
 * Chat history's own list (design-system.md § Chat history / Session
 * detail item 1) — every collection state (loading/empty/error/offline),
 * mirroring `OutfitsGrid.tsx`'s composition. Preview text (top line, with
 * the date right-aligned), message count (second line), and — only when
 * the session produced outfits — an outfit-count line in `--color-primary`
 * (third line, docs/design-decisions.md §45: never shown for a session
 * with none, including one that predates the outfit-thread link).
 */
export function HistoryList({ selectedSessionId }: HistoryListProps) {
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const isOnline = useOnlineStatus();

  const load = useCallback(async () => {
    setLoading(true);
    setError(false);
    try {
      const { data, error: fetchError } = await apiClient.GET("/api/v1/recommend/sessions");
      if (fetchError || !data) {
        setError(true);
        return;
      }
      setSessions(data.sessions);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const showError = error && isOnline; // offline suppresses the screen-level error (design-system §6)

  return (
    <>
      {loading && (
        <div className={styles.skeletonList} aria-hidden="true">
          <div className={`${styles.skeletonRow} skeleton`} />
          <div className={`${styles.skeletonRow} skeleton`} />
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

      {!loading && !error && sessions.length === 0 && (
        <div className={styles.stateBlock}>
          <p className={`textBody ${styles.stateBody}`}>
            No past conversations yet. Start styling and I&apos;ll save them here.
          </p>
          <Button href="/recommend" width="intrinsic">
            Go to Styling
          </Button>
        </div>
      )}

      {!loading && !error && sessions.length > 0 && (
        <div className={styles.list}>
          {sessions.map((session) => (
            <Link
              key={session.id}
              href={`/history/${session.id}`}
              className={[styles.row, session.id === selectedSessionId && styles.rowSelected]
                .filter(Boolean)
                .join(" ")}
            >
              <div className={styles.topLine}>
                <span className={styles.preview}>{session.preview}</span>
                <span className={styles.date}>{formatSessionDate(session.updated_at)}</span>
              </div>
              <p className={styles.messageCount}>
                {session.message_count} message{session.message_count === 1 ? "" : "s"}
              </p>
              {session.outfit_count > 0 && (
                <p className={styles.outfitCount}>
                  {session.outfit_count} outfit{session.outfit_count === 1 ? "" : "s"}
                </p>
              )}
            </Link>
          ))}
        </div>
      )}
    </>
  );
}
