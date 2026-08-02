import { ChevronLeft, ChevronRight } from "lucide-react";
import styles from "./PagerControls.module.css";

export interface PagerControlsProps {
  index: number;
  count: number;
  onPrev: () => void;
  onNext: () => void;
}

/**
 * design/design-system.md § Outfit suggestion pager, "Pager mechanics":
 * real <button>s below the card track, in their own control row with the
 * "N of M" indicator between them — never overlaid on the card. Both
 * controls and the indicator are hidden outright (not disabled) at exactly
 * one card.
 */
export function PagerControls({ index, count, onPrev, onNext }: PagerControlsProps) {
  if (count <= 1) return null;

  return (
    <div className={styles.row}>
      <button
        type="button"
        className={["control", "hitArea", styles.arrow].join(" ")}
        aria-label="Previous suggestion"
        disabled={index === 0}
        onClick={onPrev}
      >
        <ChevronLeft size={18} strokeWidth={2.1} aria-hidden="true" />
      </button>
      <span className={styles.indicator}>
        {index + 1} of {count}
      </span>
      <button
        type="button"
        className={["control", "hitArea", styles.arrow].join(" ")}
        aria-label="Next suggestion"
        disabled={index === count - 1}
        onClick={onNext}
      >
        <ChevronRight size={18} strokeWidth={2.1} aria-hidden="true" />
      </button>
    </div>
  );
}
