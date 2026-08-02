import type { components } from "@/lib/api/schema";
import styles from "./CitedRuleList.module.css";

type CitedRuleView = components["schemas"]["CitedRuleView"];

export interface CitedRuleListProps {
  citations: CitedRuleView[];
}

/**
 * Resurrects `CitedRuleList.tsx` (feature 008, removed in `b5000d7`) for
 * Outfit detail: design-system.md § Outfit detail item 2(c), a dashed
 * top-border numbered rule list below the description. Renders nothing
 * when there's nothing to cite (design-decisions.md §38's degrade path) —
 * omitting the section entirely, not an empty dashed border.
 */
export function CitedRuleList({ citations }: CitedRuleListProps) {
  if (citations.length === 0) return null;

  return (
    <ul className={styles.list}>
      {citations.map((rule) => (
        <li key={rule.number} className={styles.row}>
          <span className={styles.number}>{rule.number}</span>
          <span className={`textCaption ${styles.text}`}>{rule.text}</span>
        </li>
      ))}
    </ul>
  );
}
