import { Button } from "@/components/ui/Button/Button";
import styles from "./page.module.css";

export interface SessionActionsProps {
  sessionId: string;
  outfitCount: number;
}

/**
 * design-system.md § Chat history / Session detail item 2, closing
 * paragraph: a full-width primary "Continue conversation" (always) and —
 * only when the session produced outfits — a full-width secondary
 * "{count} → View in Outfits" below it. `sessionId` IS the thread_id
 * (docs/design-decisions.md §44) — "Continue conversation" passes it
 * straight through, no translation.
 */
export function SessionActions({ sessionId, outfitCount }: SessionActionsProps) {
  return (
    <div className={styles.actions}>
      <Button href={`/recommend?thread_id=${sessionId}`} width="full">
        Continue conversation
      </Button>
      {outfitCount > 0 && (
        <Button href="/outfits" variant="secondary" width="full">
          {outfitCount} → View in Outfits
        </Button>
      )}
    </div>
  );
}
