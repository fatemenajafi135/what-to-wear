import { Button } from "@/components/ui/Button/Button";
import styles from "./InsufficientClosetGate.module.css";

export interface InsufficientClosetGateProps {
  missing: string[];
}

function joinMissing(missing: string[]): string {
  if (missing.length === 0) return "a few more items";
  if (missing.length === 1) return missing[0]!;
  if (missing.length === 2) return `${missing[0]} and ${missing[1]}`;
  return `${missing.slice(0, -1).join(", ")}, and ${missing[missing.length - 1]}`;
}

/**
 * design-system.md `recommend.insufficient_closet.*`, resolved by
 * docs/design-decisions.md §11: names what's missing rather than a bare
 * item count. Blocks the composer entirely — this replaces the whole
 * hero/chat surface, not just disabling send.
 */
export function InsufficientClosetGate({ missing }: InsufficientClosetGateProps) {
  return (
    <div className={styles.gate}>
      <p className="textBody">
        I can&apos;t put an outfit together yet. Add {joinMissing(missing)} and I&apos;ll get started.
      </p>
      <Button href="/add" width="intrinsic">
        Add items to your closet
      </Button>
    </div>
  );
}
