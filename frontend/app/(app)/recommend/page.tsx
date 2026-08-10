"use client";

import { useEffect, useState, useSyncExternalStore } from "react";
import { useSearchParams } from "next/navigation";
import { TopHeader } from "@/components/ui/TopHeader/TopHeader";
import { IconButton } from "@/components/ui/IconButton/IconButton";
import { RecommendChat } from "@/components/recommend/RecommendChat";
import * as recommendChatStore from "@/lib/recommend/recommendChatStore";
import { apiClient } from "@/lib/api/client";
import styles from "./page.module.css";

/**
 * design/design-system.md § Screen anatomy → Recommend, item 1: TopHeader
 * plus two 36px icon-button siblings, "New chat" disabled (not hidden)
 * whenever the thread has no user turns yet. "Chat history" links to
 * `/history` (feature 011).
 *
 * specs/019-recommend-chat-persistence: conversation state lives in
 * `recommendChatStore`, not in this component or in `RecommendChat` — both
 * read/act on the same module-level store, which is what lets the
 * conversation survive this component's own unmount/remount on in-app
 * navigation. "New chat" is a direct `recommendChatStore.reset()` call, and
 * `hasUserMessage` is read straight from the store, retiring the previous
 * `forwardRef`/`useImperativeHandle` indirection into `RecommendChat`.
 *
 * `?thread_id=` (set by Session detail's "Continue conversation", feature
 * 011) resumes into that session: its own prior turns are fetched once via
 * `GET /recommend/sessions/{id}` and written into the shared store via
 * `recommendChatStore.hydrate(...)` — but only when the URL's thread_id
 * differs from whatever the store already holds (FR-005/006): resuming the
 * thread that's already active is an in-app-navigation case, not a resume,
 * and must not re-fetch or reset it. Only the caller's own `user_message`
 * turns and any zero-outfit `styling_reply` turns are replayed — an
 * outfit-bearing reply has nothing faithful to show here (its content
 * lives in the linked outfits, already read in Session detail), so it's
 * simply not re-rendered rather than shown blank or reconstructed as a
 * live pager card it never was in this page-load.
 */
export default function RecommendPage() {
  const chat = useSyncExternalStore(recommendChatStore.subscribe, recommendChatStore.getState);
  const hasUserMessage = chat.messages.some((m) => m.role === "user");
  const searchParams = useSearchParams();
  const resumeThreadId = searchParams.get("thread_id");
  const [resumeReady, setResumeReady] = useState(resumeThreadId === null || resumeThreadId === chat.threadId);

  useEffect(() => {
    if (resumeThreadId === null) {
      setResumeReady(true);
      return;
    }
    if (resumeThreadId === recommendChatStore.getState().threadId) {
      // Already the active conversation — an in-app-navigation case, not a
      // resume (FR-006). Don't re-fetch or reset it.
      setResumeReady(true);
      return;
    }
    setResumeReady(false);
    let cancelled = false;
    apiClient
      .GET("/api/v1/recommend/sessions/{session_id}", { params: { path: { session_id: resumeThreadId } } })
      .then(({ data }) => {
        if (cancelled) return;
        if (data) {
          recommendChatStore.hydrate(
            resumeThreadId,
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
                onClick={() => recommendChatStore.reset()}
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
      {resumeReady && <RecommendChat />}
    </>
  );
}
