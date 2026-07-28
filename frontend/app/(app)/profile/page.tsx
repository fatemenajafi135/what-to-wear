import { IconButton } from "@/components/ui/IconButton/IconButton";
import styles from "./page.module.css";

/**
 * Stub route — chrome + empty placeholder. Profile has no visible "Profile"
 * title text in the real design (per design/design-system.md §8), so the
 * screen's <h1> is visually hidden but still focusable for FR-009's
 * focus-on-navigate requirement.
 */
export default function ProfilePage() {
  return (
    <>
      <div className={styles.header}>
        <h1 className="visuallyHidden" tabIndex={-1}>
          Profile
        </h1>
        <IconButton icon="settings" href="/profile/settings" />
      </div>
      <div className={styles.empty}>
        <p className={`textBody ${styles.body}`}>
          Profile details aren&apos;t wired up yet in this slice — this screen
          shows its chrome only.
        </p>
      </div>
    </>
  );
}
