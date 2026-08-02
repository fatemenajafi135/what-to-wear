"use client";

import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from "react";
import { apiClient } from "@/lib/api/client";
import { Button } from "@/components/ui/Button/Button";
import { RecommendCalendarContext } from "@/components/calendar/RecommendCalendarContext";
import { HeroState } from "./HeroState";
import { ChatMessageList, type ChatMessage } from "./ChatMessageList";
import { Composer } from "./Composer";
import { StartStylingButton } from "./StartStylingButton";
import { InsufficientClosetGate } from "./InsufficientClosetGate";
import { SparseClosetBanner } from "./SparseClosetBanner";
import styles from "./RecommendChat.module.css";

type Status = "idle" | "sending" | "error";
type Readiness = { ready: boolean; sparse: boolean; missing: string[] };

export interface RecommendChatHandle {
  /** Resets to the hero state with a fresh (absent) thread_id — the
   * TopHeader's "New chat" action (docs/design-decisions.md §25: no
   * archival call in this slice, that's 011's job). */
  newChat: () => void;
}

export interface RecommendChatProps {
  /** Lets the page's TopHeader disable "New chat" on an empty thread
   * (design-system.md anatomy item 1 — visible but disabled, not hidden). */
  onHasUserMessageChange?: (hasUserMessage: boolean) => void;
}

/**
 * Owns the whole Recommend chat surface: the pending-vs-sent message split
 * and the single real network trigger ("Start styling") that docs/
 * design-decisions.md §28 resolves, and `thread_id` continuity (§25 — held
 * in memory only, never persisted, echoed on every subsequent call).
 */
export const RecommendChat = forwardRef<RecommendChatHandle, RecommendChatProps>(function RecommendChat(
  { onHasUserMessageChange },
  ref,
) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [pendingTexts, setPendingTexts] = useState<string[]>([]);
  const [threadId, setThreadId] = useState<string | null>(null);
  const [status, setStatus] = useState<Status>("idle");
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

  const hasUserMessage = messages.some((m) => m.role === "user");

  useEffect(() => {
    onHasUserMessageChange?.(hasUserMessage);
  }, [hasUserMessage, onHasUserMessageChange]);

  useImperativeHandle(ref, () => ({
    newChat: () => {
      setMessages([]);
      setPendingTexts([]);
      setThreadId(null);
      setStatus("idle");
    },
  }));

  function handleSend(text: string) {
    setMessages((prev) => [...prev, { id: crypto.randomUUID(), role: "user", text }]);
    setPendingTexts((prev) => [...prev, text]);
  }

  async function handleStartStyling() {
    if (pendingTexts.length === 0) return;
    setStatus("sending");
    const { data, error } = await apiClient.POST("/api/v1/recommend/messages", {
      body: { message: pendingTexts.join(" "), thread_id: threadId },
    });

    if (error || !data) {
      setStatus("error");
      return;
    }

    setThreadId(data.thread_id);
    setMessages((prev) => [
      ...prev,
      {
        id: crypto.randomUUID(),
        role: "assistant",
        outfits: data.outfits,
        replyText: data.reply_text,
      },
    ]);
    setPendingTexts([]);
    setStatus("idle");
  }

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
        {!hasUserMessage && <HeroState onSuggestionTap={handleSend} />}
        {hasUserMessage && <ChatMessageList messages={messages} inFlight={status === "sending"} />}

        {status === "error" && (
          <div className={styles.errorCard}>
            <p className="textBody">Something went wrong pulling that together.</p>
            <Button variant="outline" width="intrinsic" onClick={handleStartStyling}>
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
          hasPending={pendingTexts.length > 0}
          inFlight={status === "sending"}
          onClick={handleStartStyling}
        />
        <Composer onSend={handleSend} inFlight={status === "sending"} />
      </div>
    </div>
  );
});
