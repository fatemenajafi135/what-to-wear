import { TabBar } from "@/components/ui/TabBar/TabBar";
import { FocusOnNavigate } from "@/components/shell/FocusOnNavigate";
import { OfflineBanner } from "@/components/shell/OfflineBanner";
import styles from "./layout.module.css";

/**
 * The authenticated shell — persists across navigation between the four
 * primary destinations. Chrome (TabBar) is CSS-only responsive per
 * design-system.md §5; Create is composed inside TabBar at its per-tier
 * position (spec.md FR-003). OfflineBanner (feature 004) is global/
 * persistent per design-system.md §6, so it's mounted here once rather
 * than per-screen.
 */
export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <OfflineBanner />
      <TabBar />
      <FocusOnNavigate />
      <main role="main" className={styles.content}>
        {children}
      </main>
    </>
  );
}
