"use client";

import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { apiClient } from "@/lib/api/client";
import { Button } from "@/components/ui/Button/Button";
import { RecommendCalendarContext } from "@/components/calendar/RecommendCalendarContext";
import * as recommendChatStore from "@/lib/recommend/recommendChatStore";
import * as pickedEventStore from "@/lib/calendar/pickedEventStore";
import { formatEventTime } from "@/lib/calendar/formatEventTime";
import { HeroState } from "./HeroState";
import { ChatMessageList } from "./ChatMessageList";
import { Composer } from "./Composer";
import { StartStylingButton } from "./StartStylingButton";
import { InsufficientClosetGate } from "./InsufficientClosetGate";
import { SparseClosetBanner } from "./SparseClosetBanner";
import styles from "./RecommendChat.module.css";

type Readiness = { ready: boolean; sparse: boolean; missing: string[] };

/**
 * Owns the whole Recommend chat surface's rendering. Conversation state —
 * messages, accumulated composer text, `thread_id`, in-flight status —
 * lives in `recommendChatStore` (specs/019-recommend-chat-persistence), not
 * here, so it survives this component's own unmount/remount across in-app
 * navigation (GitHub issue #47). This component is a thin, store-driven
 * view: it reads via `useSyncExternalStore` and calls the store's
 * `sendTurn`/`startStyling` actions from its event handlers. "New chat" and
 * the resumed-thread hydration are both driven from `page.tsx` now, calling
 * the same store directly — see `frontend/app/(app)/recommend/page.tsx`.
 *
 * Closet readiness (`GET /recommend/readiness`) is the one piece of state
 * that stays local and refetches on every mount — deliberately NOT part of
 * the persisted store (FR-009 — it must always reflect the closet's
 * current contents, even if they changed while the user was elsewhere).
 */
export function RecommendChat() {
  const chat = useSyncExternalStore(
    recommendChatStore.subscribe,
    recommendChatStore.getState,
    recommendChatStore.getServerSnapshot,
  );
  const pickedEvent = useSyncExternalStore(
    pickedEventStore.subscribe,
    pickedEventStore.getState,
    pickedEventStore.getServerSnapshot,
  ).event;
  const [readiness, setReadiness] = useState<Readiness | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const footerRef = useRef<HTMLDivElement>(null);

  // The footer (calendar-context line + Start-styling + composer) is fixed
  // to the true bottom of the viewport so the composer is always reachable
  // without scrolling, regardless of conversation length — but its own
  // height changes (Start-styling appears/disappears, the error card comes
  // and goes), so the scrollable message list needs matching bottom
  // clearance or the fixed footer would cover the last message.
  useEffect(() => {
    const footerEl = footerRef.current;
    const scrollEl = scrollRef.current;
    if (!footerEl || !scrollEl) return;
    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (entry) scrollEl.style.paddingBottom = `${entry.contentRect.height}px`;
    });
    observer.observe(footerEl);
    return () => observer.disconnect();
  }, [readiness]);

  useEffect(() => {
    let cancelled = false;
    apiClient.GET("/api/v1/recommend/readiness").then(({ data }) => {
      if (!cancelled && data) setReadiness(data);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const hasUserMessage = chat.messages.some((m) => m.role === "user");

  // specs/020-calendar-pick-to-recommend (design-decisions.md §61): a fresh conversation
  // (no user turns yet, no active thread) with a picked event pre-fills the composer with
  // editable, unsent text built from the event's own title and time — never sent, never
  // asserted as occasion/formality fact, until the user takes an explicit send action. An
  // already-in-progress conversation is left alone (FR-011) — the same `!hasUserMessage`
  // condition that gates the hero state.
  const composerPrefill =
    !hasUserMessage && pickedEvent ? `${pickedEvent.title}, ${formatEventTime(pickedEvent.start)}` : undefined;

  if (readiness === null) {
    return (
      <div className={styles.screen}>
        <div className={styles.loadingSkeleton}>
          <div className={`skeleton ${styles.skeletonBarWide}`} />
          <div className={`skeleton ${styles.skeletonBarNarrow}`} />
        </div>
      </div>
    );
  }

  if (!readiness.ready) {
    return (
      <div className={styles.screen}>
        <InsufficientClosetGate missing={readiness.missing} />
      </div>
    );
  }

  return (
    <div className={styles.screen}>
      <div className={styles.scroll} ref={scrollRef}>
        {readiness.sparse && <SparseClosetBanner />}
        {!hasUserMessage && <HeroState onSuggestionTap={recommendChatStore.sendTurn} />}
        {hasUserMessage && (
          <ChatMessageList
            messages={chat.messages}
            turnPending={chat.turnPending}
            stylingPending={chat.startStyling === "pending"}
          />
        )}

        {chat.startStyling === "error" && (
          <div className={styles.errorCard}>
            <p className="textBody">Something went wrong pulling that together.</p>
            <Button variant="outline" width="intrinsic" onClick={recommendChatStore.startStyling}>
              Try again
            </Button>
          </div>
        )}
      </div>

      <div className={styles.footer} ref={footerRef}>
        <div className={styles.calendarContextRow}>
          <RecommendCalendarContext />
        </div>

        <StartStylingButton
          visible={hasUserMessage}
          hasPending={chat.pendingTexts.length > 0}
          inFlight={chat.turnPending || chat.startStyling === "pending"}
          onClick={recommendChatStore.startStyling}
        />
        <Composer
          onSend={recommendChatStore.sendTurn}
          inFlight={chat.turnPending || chat.startStyling === "pending"}
          initialValue={composerPrefill}
        />
      </div>
    </div>
  );
}
