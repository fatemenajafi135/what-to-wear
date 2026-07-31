import { Badge } from "@/components/ui/Badge/Badge";
import styles from "./sections.module.css";

/**
 * design-system.md §4 Connected accounts. Google Calendar always renders in
 * its disconnected appearance with an inert action — feature 012 owns the
 * OAuth flow and the real toggle (handoff §7). Weather services is
 * "Coming soon" and not interactive. No Edit/Done: nothing here is editable
 * in this feature.
 */
export function ConnectedAccountsSection() {
  return (
    <section>
      <div className={styles.header}>
        <h2 className="textSectionTitle">Connected accounts</h2>
      </div>

      <div className={styles.field} style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <p className="textBody">Google Calendar</p>
        <button type="button" className="control" disabled style={{ opacity: 0.5 }}>
          <span className="textBody">Connect</span>
        </button>
      </div>

      <div className={styles.field} style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <p className="textBody">Weather services</p>
        <Badge tone="muted">Coming soon</Badge>
      </div>
    </section>
  );
}
