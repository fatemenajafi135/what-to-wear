"use client";

import { useRouter } from "next/navigation";
import { TopHeader } from "@/components/ui/TopHeader/TopHeader";
import { HistoryList } from "./HistoryList";
import styles from "./page.module.css";

/**
 * `/history` — the list pane (design-system.md § Chat history / Session
 * detail item 1): sticky `TopHeader` (title "Chat history", back arrow,
 * right slot = pill "New chat"). At ≥1024px (§5's two-pane master-detail)
 * it renders beside a placeholder detail pane; below that it's the whole
 * screen and `/history/:sessionId` is reached by push navigation (mirrors
 * `/outfits/page.tsx` exactly).
 *
 * "New chat" needs no archive call of its own (design-decisions.md §44 —
 * every thread with a user turn is already durable from its first
 * message) — it only has to land the user back in Recommend with a fresh,
 * absent thread, which a bare `/recommend` visit already is.
 */
export default function HistoryPage() {
  const router = useRouter();

  return (
    <div className={styles.twoPane}>
      <div>
        <TopHeader
          title="Chat history"
          backHref="/recommend"
          rightSlot={{ kind: "pill", label: "New chat", onClick: () => router.push("/recommend") }}
        />
        <HistoryList />
      </div>
      <div className={styles.detailPane}>
        <p className="textBody">Select a conversation to view it.</p>
      </div>
    </div>
  );
}
