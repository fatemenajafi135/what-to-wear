"use client";

import { Badge } from "@/components/ui/Badge/Badge";
import { Button } from "@/components/ui/Button/Button";
import { useCalendarConnection } from "@/lib/calendar/useCalendarConnection";
import styles from "./sections.module.css";

/**
 * design-system.md §4 Connected accounts: Google Calendar shows a "Connected"
 * status Badge when linked and a "Connect" text action when not. Weather
 * services is "Coming soon" and not interactive. No Edit/Done — nothing here
 * is a draft; each action commits immediately.
 *
 * Both this row and `/calendar`'s own connect action read and write the same
 * state through `useCalendarConnection`, never a second independent fetch —
 * the "two entry points, one state" requirement in
 * docs/handoffs/012-calendar.md §6.4. Feature 013 shipped this row inert
 * because 012 owned the OAuth flow and had not merged; 012 built the hook for
 * exactly this row but could not wire it, because 013 had not merged either.
 * Connected here at the merge, which is the first point both halves existed.
 */
export function ConnectedAccountsSection() {
  const { connected, isLoading, connect, disconnect } = useCalendarConnection();

  return (
    <section>
      <div className={styles.header}>
        <h2 className="textSectionTitle">Connected accounts</h2>
      </div>

      <div className={`${styles.field} ${styles.rowBetween}`}>
        <p className="textBody">Google Calendar</p>
        {isLoading ? (
          // Fail closed while the real state is unknown, matching how the
          // Google sign-in button gates itself (design-decisions.md §15):
          // never offer an action that is about to be rejected.
          <Button variant="outline" width="intrinsic" disabled>
            Connect
          </Button>
        ) : connected ? (
          <span className={styles.rowBetween}>
            <Badge tone="status">Connected</Badge>
            <Button variant="outline" width="intrinsic" onClick={() => void disconnect()}>
              Disconnect
            </Button>
          </span>
        ) : (
          <Button variant="outline" width="intrinsic" onClick={() => void connect()}>
            Connect
          </Button>
        )}
      </div>

      <div className={`${styles.field} ${styles.rowBetween}`}>
        <p className="textBody">Weather services</p>
        <Badge tone="muted">Coming soon</Badge>
      </div>
    </section>
  );
}
