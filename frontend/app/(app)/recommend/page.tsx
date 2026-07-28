import { TopHeader } from "@/components/ui/TopHeader/TopHeader";
import styles from "./page.module.css";

/**
 * Stub route — chrome only. The chat/hero experience (greeting, suggestion
 * chips, composer) belongs to the Recommend/styling feature, not this
 * app-shell slice (out of scope, see spec.md).
 */
export default function RecommendPage() {
  return (
    <>
      <TopHeader
        title="Styling"
        subtitle="Ask for an outfit, get cited picks from your closet"
      />
      <div className={styles.empty}>
        <p className={`textBody ${styles.body}`}>
          The styling assistant isn&apos;t wired up yet in this slice — this screen
          shows its chrome only.
        </p>
      </div>
    </>
  );
}
