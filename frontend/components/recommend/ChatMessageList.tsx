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
  /** The reply's own thread_id — threaded down to the pager's save call so
   * it can capture citations/dimension scores server-side from this
   * thread's checkpointed state (design-decisions.md §38). */
  threadId?: string;
}

export interface ChatMessageListProps {
  messages: ChatMessage[];
  /** A Start-styling request is in flight — shows the pager's own inline
   * skeleton card (design-system.md § Outfit suggestion pager, Loading
   * group-state) in place of the old plain "Thinking…" caption, which the
   * design system reserves for a different, non-generation acknowledgment. */
  inFlight: boolean;
}

/**
 * design/design-system.md § Screen anatomy → Recommend, item 3 / § Outfit
 * suggestion pager. Every outfit-bearing reply — including exactly one
 * outfit — now renders through the pager (design-decisions.md §35); there
 * is no remaining single-flat-card/inline-citation path for an outfit
 * reply. A reply with zero outfits renders the group's own Empty message
 * (the backend's `reply_text`, verbatim — either the pipeline's own honesty
 * note or the generic "not surfaced" copy) plus a recovery link to Add
 * item, following the standard empty-state explain+action convention,
 * instead of an empty pager track.
 */
export function ChatMessageList({ messages, inFlight }: ChatMessageListProps) {
  return (
    <div className={styles.list}>
      {messages.map((message) =>
        message.role === "user" ? (
          <div key={message.id} className={styles.userBubble}>
            <p className="textBody">{message.text}</p>
          </div>
        ) : message.outfits && message.outfits.length > 0 ? (
          <div key={message.id} className={styles.assistantGroup}>
            <SuggestionPager outfits={message.outfits} threadId={message.threadId ?? ""} />
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
      {inFlight && <PagerSkeletonCard />}
    </div>
  );
}
