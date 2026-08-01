"use client";

import { useRef, useState } from "react";
import { TopHeader } from "@/components/ui/TopHeader/TopHeader";
import { IconButton } from "@/components/ui/IconButton/IconButton";
import { RecommendChat, type RecommendChatHandle } from "@/components/recommend/RecommendChat";
import styles from "./page.module.css";

/**
 * design/design-system.md § Screen anatomy → Recommend, item 1: TopHeader
 * plus two 36px icon-button siblings, "New chat" disabled (not hidden)
 * whenever the thread has no user turns yet. "Chat history"'s destination
 * is feature 011 — no /history route exists yet, so the control is wired
 * inert rather than linking to a 404 (handoff's own guidance for this
 * exact situation).
 */
export default function RecommendPage() {
  const chatRef = useRef<RecommendChatHandle>(null);
  const [hasUserMessage, setHasUserMessage] = useState(false);

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
              <IconButton icon="history" size={36} disabled aria-disabled="true" />
            </div>
          ),
        }}
      />
      <RecommendChat ref={chatRef} onHasUserMessageChange={setHasUserMessage} />
    </>
  );
}
