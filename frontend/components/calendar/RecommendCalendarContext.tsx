"use client";

import { useEffect, useSyncExternalStore } from "react";
import Link from "next/link";
import { CalendarIcon } from "lucide-react";
import * as pickedEventStore from "@/lib/calendar/pickedEventStore";
import styles from "./RecommendCalendarContext.module.css";

/**
 * design/design-system.md "Screen anatomy → Recommend", point 4: "Style for
 * an event from calendar" (nothing picked) or "Styling for {event} ·
 * Change" (picked, with a small calendar glyph). Feature 012's one touch to
 * /recommend (feature 008's screen) — see the feature 012 report for
 * exactly what was added here.
 *
 * specs/020-calendar-pick-to-recommend (issue #41 defect 2): this used to
 * fetch `/calendar/picked-event` itself, once, in a mount-scoped effect —
 * stale for minutes because Next's Router Cache serves `/recommend` without
 * remounting on in-app navigation, so the effect never reran. It now reads
 * `pickedEventStore` (write-through — see that module's docstring), which
 * is updated the instant a pick is confirmed elsewhere in the app, with no
 * dependency on this component's own mount timing.
 */
export function RecommendCalendarContext() {
  const { status, event } = useSyncExternalStore(
    pickedEventStore.subscribe,
    pickedEventStore.getState,
    pickedEventStore.getServerSnapshot,
  );

  useEffect(() => {
    if (status === "unknown") {
      pickedEventStore.hydrate();
    }
  }, [status]);

  if (event) {
    return (
      <Link href="/calendar" className={`textBody ${styles.link}`}>
        <CalendarIcon size={14} aria-hidden="true" />
        Styling for {event.title} · Change
      </Link>
    );
  }

  return (
    <Link href="/calendar" className={`textBody ${styles.link}`}>
      Style for an event from calendar
    </Link>
  );
}
