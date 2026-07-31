"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { CalendarIcon } from "lucide-react";
import { apiClient } from "@/lib/api/client";
import styles from "./RecommendCalendarContext.module.css";

/**
 * design/design-system.md "Screen anatomy → Recommend", point 4: "Style for
 * an event from calendar" (nothing picked) or "Styling for {event} ·
 * Change" (picked, with a small calendar glyph). Feature 012's one touch to
 * /recommend (feature 008's screen) — see the feature 012 report for
 * exactly what was added here.
 */
export function RecommendCalendarContext() {
  const [pickedTitle, setPickedTitle] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    apiClient.GET("/api/v1/calendar/picked-event").then(({ data }) => {
      if (!cancelled && data?.picked && data.event) {
        setPickedTitle(data.event.title);
      }
    });
    return () => {
      cancelled = true;
    };
  }, []);

  if (pickedTitle) {
    return (
      <Link href="/calendar" className={`textBody ${styles.link}`}>
        <CalendarIcon size={14} aria-hidden="true" />
        Styling for {pickedTitle} · Change
      </Link>
    );
  }

  return (
    <Link href="/calendar" className={`textBody ${styles.link}`}>
      Style for an event from calendar
    </Link>
  );
}
