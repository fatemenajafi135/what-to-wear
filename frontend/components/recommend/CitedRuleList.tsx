import type { components } from "@/lib/api/schema";
import styles from "./CitedRuleList.module.css";

type CitedRule = components["schemas"]["CitedRule"];

export interface CitedRuleListProps {
  citations: CitedRule[];
}

/**
 * design/design-system.md § Screen anatomy → Recommend, item 3: dashed
 * top-border rule list below the thumbnail row, one numbered row per cited
 * rule.
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
