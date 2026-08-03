import { Fragment } from "react";
import { Badge } from "@/components/ui/Badge/Badge";
import type { components } from "@/lib/api/schema";
import chatStyles from "@/components/recommend/ChatMessageList.module.css";

type SessionMessageView = components["schemas"]["SessionMessageView"];

const CITATION_TOKEN = /\[(\d+)]/g;

/** Same token-splitting logic as `RationaleWithCitations.tsx` — lifted
 * rather than imported across route groups, since both are small, stable,
 * and this file has no other dependency on the Outfits route. */
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

export interface SessionMessagesProps {
  messages: SessionMessageView[];
}

/**
 * The archived, read-only transcript (design-system.md § Chat history /
 * Session detail item 2) — same user/assistant bubble treatment as
 * Recommend (`ChatMessageList.module.css`'s own classes, reused directly
 * rather than duplicated), including citation badges — but deliberately
 * **no item-thumbnail rows and no rule list** (docs/design-decisions.md
 * §46: badges render from each linked outfit's own already-grounded
 * `rationale_with_citations`, never a reproduction of the live pager or
 * Outfit detail's fuller treatment). A `styling_reply` turn with no linked
 * outfits renders its plain `text` (the honest empty-citation/nothing-
 * surfaced copy) with no badge at all.
 */
export function SessionMessages({ messages }: SessionMessagesProps) {
  return (
    <div className={chatStyles.list}>
      {messages.map((message) =>
        message.role === "user" ? (
          <div key={message.id} className={chatStyles.userBubble}>
            <p className="textBody">{message.text}</p>
          </div>
        ) : (
          <div key={message.id} className={chatStyles.assistantGroup}>
            {message.outfits.length > 0 ? (
              message.outfits.map((outfit) => (
                <div key={outfit.id} className={chatStyles.assistantBubble}>
                  <p className="textBody">{renderWithCitations(outfit.rationale_with_citations)}</p>
                </div>
              ))
            ) : (
              <div className={chatStyles.assistantBubble}>
                <p className="textBody">{message.text}</p>
              </div>
            )}
          </div>
        ),
      )}
    </div>
  );
}
