import { Fragment } from "react";
import { Badge } from "@/components/ui/Badge/Badge";
import type { components } from "@/lib/api/schema";
import { ItemThumbnailRow } from "./ItemThumbnailRow";
import { CitedRuleList } from "./CitedRuleList";
import styles from "./ChatMessageList.module.css";

type StylingOutfit = components["schemas"]["StylingOutfit"];
type CitedRule = components["schemas"]["CitedRule"];

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  text?: string;
  outfit?: StylingOutfit | null;
  citations?: CitedRule[];
}

export interface ChatMessageListProps {
  messages: ChatMessage[];
  /** A Start-styling request is in flight — shows the trailing "Thinking…" row. */
  inFlight: boolean;
}

const CITATION_TOKEN = /\[(\d+)]/g;

function renderWithCitations(text: string) {
  const parts: (string | number)[] = [];
  let lastIndex = 0;
  for (const match of text.matchAll(CITATION_TOKEN)) {
    const index = match.index ?? 0;
    if (index > lastIndex) parts.push(text.slice(lastIndex, index));
    parts.push(Number(match[1]));
    lastIndex = index + match[0].length;
  }
  if (lastIndex < text.length) parts.push(text.slice(lastIndex));

  return parts.map((part, i) =>
    typeof part === "number" ? (
      <Badge key={i} tone="citation">
        {part}
      </Badge>
    ) : (
      <Fragment key={i}>{part}</Fragment>
    ),
  );
}

/**
 * design/design-system.md § Screen anatomy → Recommend, item 3. User
 * bubbles right-aligned/primary; assistant bubbles left-aligned/
 * surface-sunken, with inline numbered citation Badges parsed out of
 * `[n]`-style tokens the backend embeds in `rationale_text`
 * (specs/008-styling-chat/data-model.md). Citations live in the bubble,
 * never on a card (§ Badge) — there is no separate outfit-card component in
 * this single-outfit-reply feature, only this bubble + thumbnail row + rule
 * list.
 */
export function ChatMessageList({ messages, inFlight }: ChatMessageListProps) {
  return (
    <div className={styles.list}>
      {messages.map((message) =>
        message.role === "user" ? (
          <div key={message.id} className={styles.userBubble}>
            <p className="textBody">{message.text}</p>
          </div>
        ) : (
          <div key={message.id} className={styles.assistantGroup}>
            <div className={styles.assistantBubble}>
              <p className="textBody">{renderWithCitations(message.text ?? "")}</p>
            </div>
            {message.outfit && <ItemThumbnailRow items={message.outfit.items} />}
            {message.citations && <CitedRuleList citations={message.citations} />}
          </div>
        ),
      )}
      {inFlight && (
        <div className={styles.assistantBubble} role="status" aria-live="polite">
          <p className="textBody">Thinking…</p>
        </div>
      )}
    </div>
  );
}
