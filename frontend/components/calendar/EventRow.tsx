import { formatEventTime } from "@/lib/calendar/formatEventTime";
import styles from "./EventRow.module.css";

export interface EventRowProps {
  title: string;
  start: string;
  location: string | null;
  disabled: boolean;
  onSelect: () => void;
}

/**
 * design/design-system.md §6 Calendar: title on its own line, then a
 * `{time} · {location}` meta line. Once any event is picked, every row
 * (including the picked one) renders disabled — opacity 0.5,
 * cursor: not-allowed — with no "selected" highlight, per the same spec.
 */
export function EventRow({ title, start, location, disabled, onSelect }: EventRowProps) {
  const meta = location ? `${formatEventTime(start)} · ${location}` : formatEventTime(start);

  return (
    <button
      type="button"
      className={`control ${styles.row}`}
      onClick={onSelect}
      disabled={disabled}
      aria-label={`Style for ${title}, ${meta}`}
    >
      <span className={`textCardTitle ${styles.title}`}>{title}</span>
      <span className={`textCaption ${styles.meta}`}>{meta}</span>
    </button>
  );
}
