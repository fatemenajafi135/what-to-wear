import { IconButton, type IconKeyword } from "@/components/ui/IconButton/IconButton";
import styles from "./TopHeader.module.css";

export type TopHeaderRightSlot =
  | { kind: "none" }
  | { kind: "icon"; icon: IconKeyword; onClick: () => void; label?: string }
  | { kind: "pill"; label: string; onClick: () => void }
  | { kind: "custom"; node: React.ReactNode };

export interface TopHeaderProps {
  title: string;
  subtitle?: string;
  onBack?: () => void;
  /** Renders the back IconButton as a Link when a client onBack handler isn't needed. */
  backHref?: string;
  rightSlot?: TopHeaderRightSlot;
  /** id applied to the <h1> so a route-change effect can focus it (FR-009) */
  headingId?: string;
}

/**
 * design/design-system.md §3 TopHeader. Title renders as the screen's <h1>
 * with tabIndex={-1} so a navigation effect can move focus to it without
 * joining the tab order (design-system.md §8). Title/subtitle ellipsis
 * truncate.
 */
export function TopHeader({
  title,
  subtitle,
  onBack,
  backHref,
  rightSlot = { kind: "none" },
  headingId,
}: TopHeaderProps) {
  return (
    <header className={styles.header}>
      {backHref ? (
        <IconButton icon="back" href={backHref} />
      ) : (
        onBack && <IconButton icon="back" onClick={onBack} />
      )}
      <div className={styles.titleGroup}>
        <h1 id={headingId} tabIndex={-1} className={`textScreenTitle ${styles.title}`}>
          {title}
        </h1>
        {subtitle && <p className={`textCaption ${styles.subtitle}`}>{subtitle}</p>}
      </div>
      {rightSlot.kind === "icon" && (
        <div className={styles.rightSlot}>
          <IconButton icon={rightSlot.icon} onClick={rightSlot.onClick} label={rightSlot.label} />
        </div>
      )}
      {rightSlot.kind === "pill" && (
        <button type="button" className={styles.pillButton} onClick={rightSlot.onClick}>
          {rightSlot.label}
        </button>
      )}
      {rightSlot.kind === "custom" && <div className={styles.rightSlot}>{rightSlot.node}</div>}
    </header>
  );
}
