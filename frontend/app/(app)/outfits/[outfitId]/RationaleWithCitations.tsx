import { Fragment } from "react";
import { Badge } from "@/components/ui/Badge/Badge";

const CITATION_TOKEN = /\[(\d+)]/g;

/**
 * Resurrects `renderWithCitations` from `ChatMessageList.tsx` (feature 008,
 * removed in commit `b5000d7` once 009 moved every outfit reply onto the
 * citation-free pager) — parses `[n]`-style tokens out of
 * `rationale_with_citations` and renders each as a numbered citation
 * `Badge`. Outfit detail is now the shape's only remaining consumer
 * (design-decisions.md §38).
 */
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

export interface RationaleWithCitationsProps {
  rationaleText: string;
  rationaleWithCitations: string;
}

/**
 * design/design-system.md § Outfit detail item 2(b): the styling
 * description as plain text with inline numbered citation Badges — this is
 * citations' only home (§ Badge). Falls back to plain `rationaleText` with
 * no markers when `rationaleWithCitations` is empty (the honest
 * nothing-to-cite/no-longer-provable case, design-decisions.md §38's
 * degrade path) — never a broken or fabricated reference.
 */
export function RationaleWithCitations({ rationaleText, rationaleWithCitations }: RationaleWithCitationsProps) {
  const text = rationaleWithCitations || rationaleText;
  return <p className="textBody">{renderWithCitations(text)}</p>;
}
