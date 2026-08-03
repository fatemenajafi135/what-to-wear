"use client";

import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { TopHeader } from "@/components/ui/TopHeader/TopHeader";
import { IconButton } from "@/components/ui/IconButton/IconButton";
import { RecommendChat, type RecommendChatHandle } from "@/components/recommend/RecommendChat";
import type { ChatMessage } from "@/components/recommend/ChatMessageList";
import { apiClient } from "@/lib/api/client";
import styles from "./page.module.css";

/**
 * design/design-system.md § Screen anatomy → Recommend, item 1: TopHeader
 * plus two 36px icon-button siblings, "New chat" disabled (not hidden)
 * whenever the thread has no user turns yet. "Chat history" links to
 * `/history` (feature 011).
 *
 * `?thread_id=` (set by Session detail's "Continue conversation", feature
 * 011) resumes into that session: its own prior turns are fetched once via
 * `GET /recommend/sessions/{id}` and handed to `RecommendChat` as initial
 * state, so the next message this component sends carries the resumed
 * `thread_id` rather than a freshly minted one (docs/design-decisions.md
 * §44/§45). Only the caller's own `user_message` turns and any
 * zero-outfit `styling_reply` turns are replayed — an outfit-bearing reply
 * has nothing faithful to show here (its content lives in the linked
 * outfits, already read in Session detail), so it's simply not
 * re-rendered rather than shown blank or reconstructed as a live pager
 * card it never was in this page-load.
 */
export default function RecommendPage() {
  const chatRef = useRef<RecommendChatHandle>(null);
  const [hasUserMessage, setHasUserMessage] = useState(false);
  const searchParams = useSearchParams();
  const resumeThreadId = searchParams.get("thread_id");
  const [resumeReady, setResumeReady] = useState(resumeThreadId === null);
  const [resumedMessages, setResumedMessages] = useState<ChatMessage[]>([]);

  useEffect(() => {
    if (resumeThreadId === null) return;
    let cancelled = false;
    apiClient
      .GET("/api/v1/recommend/sessions/{session_id}", { params: { path: { session_id: resumeThreadId } } })
      .then(({ data }) => {
        if (cancelled) return;
        if (data) {
          setResumedMessages(
            data.messages
              .filter((m) => m.kind === "user_message" || m.outfits.length === 0)
              .map((m) => ({
                id: m.id,
                role: m.role,
                text: m.role === "user" ? m.text : undefined,
                replyText: m.role === "assistant" ? m.text : undefined,
              })),
          );
        }
        setResumeReady(true);
      });
    return () => {
      cancelled = true;
    };
  }, [resumeThreadId]);

  return (
    <>
      <TopHeader
        title="Styling"
        subtitle="Ask for an outfit, get cited picks from your closet"
        rightSlot={{
          kind: "custom",
          node: (
            <div className={styles.headerActions}>
              <IconButton
                icon="newChat"
                size={36}
                disabled={!hasUserMessage}
                onClick={() => chatRef.current?.newChat()}
              />
              <IconButton icon="history" size={36} href="/history" />
            </div>
          ),
        }}
      />
      {!resumeReady && (
        <div className={styles.resumeLoading} aria-hidden="true">
          <div className={`${styles.resumeSkeleton} skeleton`} />
        </div>
      )}
      {resumeReady && (
        <RecommendChat
          ref={chatRef}
          onHasUserMessageChange={setHasUserMessage}
          initialThreadId={resumeThreadId}
          initialMessages={resumedMessages}
        />
      )}
    </>
  );
}
