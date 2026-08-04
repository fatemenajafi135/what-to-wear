import Link from "next/link";
import type { components } from "@/lib/api/schema";
import { PagerSkeletonCard } from "./PagerSkeletonCard";
import { SuggestionPager } from "./SuggestionPager";
import styles from "./ChatMessageList.module.css";

type StylingOutfit = components["schemas"]["StylingOutfit"];

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  text?: string;
  outfits?: StylingOutfit[];
  replyText?: string | null;
  /** feature 016 — true for an ordinary conversational reply or the
   * Start-styling wrap-up: a plain bubble with no "Add items" recovery
   * link, distinct from a Start-styling reply that produced zero outfits
   * (design-decisions.md §49; docs/handoffs/016-conversational-turns.md §4.3). */
  plain?: boolean;
}

export interface ChatMessageListProps {
  messages: ChatMessage[];
  /** A conversational turn (`POST /recommend/turns`) is in flight — shows
   * the "Thinking…" bubble (design-system.md § Chat input behavior),
   * distinct from `stylingPending`'s own "Styling your outfit…" skeleton. */
  turnPending: boolean;
  /** A Start-styling request is in flight — shows the pager's own inline
   * skeleton card (design-system.md § Outfit suggestion pager, Loading
   * group-state) in place of a plain caption. */
  stylingPending: boolean;
}

/**
 * design/design-system.md § Screen anatomy → Recommend, item 3 / § Outfit
 * suggestion pager. Every outfit-bearing reply — including exactly one
 * outfit — now renders through the pager (design-decisions.md §35); there
 * is no remaining single-flat-card/inline-citation path for an outfit
 * reply. A Start-styling reply with zero outfits renders the group's own
 * Empty message (the backend's `reply_text`, verbatim — either the
 * pipeline's own honesty note or the generic "not surfaced" copy) plus a
 * recovery link to Add item. An ordinary conversational reply or the
 * wrap-up (`message.plain`) renders the same bubble shape with no such
 * link — there is nothing to recover from.
 */
export function ChatMessageList({ messages, turnPending, stylingPending }: ChatMessageListProps) {
  return (
    <div className={styles.list}>
      {messages.map((message) =>
        message.role === "user" ? (
          <div key={message.id} className={styles.userBubble}>
            <p className="textBody">{message.text}</p>
          </div>
        ) : message.outfits && message.outfits.length > 0 ? (
          <div key={message.id} className={styles.assistantGroup}>
            <SuggestionPager outfits={message.outfits} />
          </div>
        ) : message.plain ? (
          <div key={message.id} className={styles.assistantGroup}>
            <div className={styles.assistantBubble}>
              <p className="textBody">{message.replyText}</p>
            </div>
          </div>
        ) : (
          <div key={message.id} className={styles.assistantGroup}>
            <div className={styles.assistantBubble}>
              <p className="textBody">{message.replyText}</p>
            </div>
            <Link href="/add" className={styles.addItemLink}>
              Add items to your closet
            </Link>
          </div>
        ),
      )}
      {turnPending && (
        <div className={styles.assistantGroup} role="status">
          <div className={styles.assistantBubble}>
            <p className="textBody">Thinking…</p>
          </div>
        </div>
      )}
      {stylingPending && <PagerSkeletonCard />}
    </div>
  );
}
