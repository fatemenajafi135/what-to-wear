import { TopHeader } from "@/components/ui/TopHeader/TopHeader";
import styles from "./page.module.css";

const SECTIONS = [
  "Style preferences",
  "Body & size",
  "Account",
  "Connected accounts",
  "Notifications",
];

/**
 * Stub route — chrome + a static section list, per design/design-system.md
 * §4's in-page section switcher. No live fields are wired this slice (no
 * real data/forms) — each section will become interactive in a later
 * feature.
 */
export default function SettingsPage() {
  return (
    <>
      <TopHeader title="Settings" backHref="/profile" />
      <ul className={styles.sectionList}>
        {SECTIONS.map((section) => (
          <li key={section} className={`textBody ${styles.sectionRow}`}>
            {section}
          </li>
        ))}
      </ul>
    </>
  );
}
