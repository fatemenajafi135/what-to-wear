"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { CalendarIcon } from "lucide-react";
import { TopHeader } from "@/components/ui/TopHeader/TopHeader";
import { Button } from "@/components/ui/Button/Button";
import { Banner } from "@/components/ui/Banner/Banner";
import { CalendarPrimer } from "@/components/calendar/CalendarPrimer";
import { EventRow } from "@/components/calendar/EventRow";
import { apiClient } from "@/lib/api/client";
import { useCalendarConnection } from "@/lib/calendar/useCalendarConnection";
import { isCalendarPrimed, setCalendarPrimed } from "@/lib/calendar/primed";
import { useOnlineStatus } from "@/lib/useOnlineStatus";
import * as pickedEventStore from "@/lib/calendar/pickedEventStore";
import styles from "./page.module.css";

interface CalendarEventView {
  google_event_id: string;
  title: string;
  start: string;
  location: string | null;
}

/**
 * design/design-system.md §6 Calendar + "Screen anatomy → Calendar":
 * disconnected / connected-with-events / connected-empty / error, plus
 * loading (skeleton) and offline (global banner, screen error suppressed
 * per §6's precedence rule).
 */
export default function CalendarPage() {
  const { connected, isLoading: connectionLoading, connect } = useCalendarConnection();
  const isOnline = useOnlineStatus();
  const router = useRouter();

  const [showPrimer, setShowPrimer] = useState(false);
  const [events, setEvents] = useState<CalendarEventView[] | null>(null);
  const [eventsError, setEventsError] = useState(false);
  const [eventsLoading, setEventsLoading] = useState(false);
  const [pickedEventId, setPickedEventId] = useState<string | null>(null);
  // In flight for exactly one PUT (defect 1) — distinct from `pickedEventId`, which is only
  // ever set once a pick is actually confirmed saved. Rows dim for both (§609's existing
  // "any pick disables every row" behavior), but only a confirmed pick is durable.
  const [savingEventId, setSavingEventId] = useState<string | null>(null);
  const [pickError, setPickError] = useState<CalendarEventView | null>(null);

  const loadEvents = useCallback(async () => {
    setEventsLoading(true);
    setEventsError(false);
    const [eventsResult, pickedResult] = await Promise.all([
      apiClient.GET("/api/v1/calendar/events"),
      apiClient.GET("/api/v1/calendar/picked-event"),
    ]);
    if (eventsResult.error || !eventsResult.data) {
      setEventsError(true);
      setEvents(null);
    } else {
      setEvents(eventsResult.data.events);
    }
    if (pickedResult.data?.picked && pickedResult.data.event) {
      setPickedEventId(pickedResult.data.event.google_event_id);
    }
    setEventsLoading(false);
  }, []);

  useEffect(() => {
    if (connected) {
      loadEvents();
    }
  }, [connected, loadEvents]);

  const handleConnectClick = () => {
    if (isCalendarPrimed()) {
      connect();
    } else {
      setShowPrimer(true);
    }
  };

  const handlePrimerContinue = () => {
    setCalendarPrimed();
    setShowPrimer(false);
    connect();
  };

  const handlePick = async (event: CalendarEventView) => {
    setSavingEventId(event.google_event_id);
    setPickError(null);
    const { data, error } = await apiClient.PUT("/api/v1/calendar/picked-event", {
      body: {
        google_event_id: event.google_event_id,
        title: event.title,
        start: event.start,
        location: event.location,
      },
    });
    setSavingEventId(null);

    // Check the result rather than discarding it (issue #41 defect 1) — a failed save must
    // never look like a successful one. Nothing is marked picked, and no navigation happens,
    // until the backend actually confirms it.
    if (error || !data?.event) {
      setPickError(event);
      return;
    }

    pickedEventStore.set(data.event);
    setPickedEventId(data.event.google_event_id);
    router.push("/recommend");
  };

  const handleRetry = () => {
    loadEvents();
  };

  return (
    <>
      <TopHeader title="Calendar events" backHref="/recommend" />

      {(connectionLoading || (connected && eventsLoading)) && (
        <div className={styles.skeletonList} aria-hidden="true">
          <div className={`skeleton ${styles.skeletonRow}`} />
          <div className={`skeleton ${styles.skeletonRow}`} />
        </div>
      )}

      {!connectionLoading && !connected && (
        <div className={styles.disconnected}>
          <div className={styles.iconTile}>
            <CalendarIcon aria-hidden="true" />
          </div>
          <h2 className="textSectionTitle">Connect your calendar</h2>
          <p className={`textBody ${styles.body}`}>
            Link Google Calendar so I can suggest outfits for what is actually on your
            schedule.
          </p>
          <Button onClick={handleConnectClick}>Connect Google Calendar</Button>
        </div>
      )}

      {connected && !eventsLoading && eventsError && isOnline && (
        <div className={styles.disconnected}>
          <p className={`textBody ${styles.body}`}>Couldn&apos;t sync your calendar.</p>
          <Button width="intrinsic" onClick={handleRetry}>
            Retry
          </Button>
        </div>
      )}

      {connected && !eventsLoading && !eventsError && events && events.length === 0 && (
        <div className={styles.disconnected}>
          <p className={`textBody ${styles.body}`}>
            Nothing on your calendar this week. Ask me to style for any plan instead.
          </p>
          <Button href="/recommend" width="intrinsic">
            Style something
          </Button>
        </div>
      )}

      {connected && !eventsLoading && !eventsError && events && events.length > 0 && (
        <div className={styles.list}>
          <p className={`textCaption ${styles.hint}`}>Pick an upcoming event to style for.</p>
          {pickError && (
            <Banner variant="error" action={{ label: "Try again", onClick: () => handlePick(pickError) }}>
              Couldn&apos;t save that pick.
            </Banner>
          )}
          {events.map((event) => (
            <EventRow
              key={event.google_event_id}
              title={event.title}
              start={event.start}
              location={event.location}
              disabled={pickedEventId !== null || savingEventId !== null}
              onSelect={() => handlePick(event)}
            />
          ))}
        </div>
      )}

      <CalendarPrimer
        open={showPrimer}
        onContinue={handlePrimerContinue}
        onDismiss={() => setShowPrimer(false)}
      />
    </>
  );
}
