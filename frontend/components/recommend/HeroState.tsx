"use client";

import { Chip } from "@/components/ui/Chip/Chip";
import { useGreeting } from "./useGreeting";
import styles from "./HeroState.module.css";

const SUGGESTION_CHIPS = ["Rainy day commute", "Dinner date outfit", "Business casual"];

export interface HeroStateProps {
  onSuggestionTap: (text: string) => void;
}

/**
 * design/design-system.md § Screen anatomy → Recommend, item 2. Copy check
 * (FR-018): the welcome bubble makes no personalization/past-feedback claim
 * — preference memory is inert this slice (handoff §2.2).
 */
export function HeroState({ onSuggestionTap }: HeroStateProps) {
  const greeting = useGreeting();

  return (
    <div className={styles.hero}>
      {/* eslint-disable-next-line @next/next/no-img-element -- static brand asset, not optimizable content */}
      <img src="/mark.svg" alt="" width={60} height={60} className={styles.mark} />
      <p className={`textDisplay ${styles.wordmark}`}>What to Wear</p>
      <p className={styles.greeting}>{greeting}</p>

      <div className={styles.welcomeBubble}>
        <p className="textBody">
          Ask me for an outfit and I&apos;ll build one from your own closet, with reasoning you can
          check.
        </p>
      </div>

      <div className={styles.chips}>
        {SUGGESTION_CHIPS.map((label) => (
          <Chip key={label} type="button" onClick={() => onSuggestionTap(label)}>
            {label}
          </Chip>
        ))}
      </div>
    </div>
  );
}
