"use client";

import { useEffect, useState } from "react";
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

/**
 * Owns the whole Recommend chat surface: the pending-vs-sent message split
 * and the single real network trigger ("Start styling") that docs/
 * design-decisions.md §28 resolves, and `thread_id` continuity (§25 — held
 * in memory only, never persisted, echoed on every subsequent call).
 */
export function RecommendChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [pendingTexts, setPendingTexts] = useState<string[]>([]);
  const [threadId, setThreadId] = useState<string | null>(null);
  const [status, setStatus] = useState<Status>("idle");
  const [readiness, setReadiness] = useState<Readiness | null>(null);

  useEffect(() => {
    let cancelled = false;
    apiClient.GET("/api/v1/recommend/readiness").then(({ data }) => {
      if (!cancelled && data) setReadiness(data);
    });
    return () => {
      cancelled = true;
    };
  }, []);

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
        text: data.outfit ? data.outfit.rationale_text : (data.reply_text ?? ""),
        outfit: data.outfit,
        citations: data.citations,
      },
    ]);
    setPendingTexts([]);
    setStatus("idle");
  }

  const hasUserMessage = messages.some((m) => m.role === "user");

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
      <div className={styles.scroll}>
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
  );
}
