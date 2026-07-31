"use client";

import { useState } from "react";
import { Switch } from "@/components/ui/Switch/Switch";
import { updateNotifications, type ProfileResponse } from "@/lib/api/profile";
import styles from "./sections.module.css";

interface Props {
  profile: ProfileResponse;
  disabled: boolean;
  onSaved: (profile: ProfileResponse) => void;
}

/**
 * design-system.md §4 Notifications — the one section with no Edit/Done;
 * the switch commits immediately (FR-009).
 */
export function NotificationsSection({ profile, disabled, onSaved }: Props) {
  const [saving, setSaving] = useState(false);
  const checked = profile.notifications_enabled ?? true;

  async function toggle(next: boolean) {
    setSaving(true);
    try {
      const updated = await updateNotifications({ notifications_enabled: next });
      onSaved(updated);
    } finally {
      setSaving(false);
    }
  }

  return (
    <section>
      <div className={styles.header}>
        <h2 className="textSectionTitle">Notifications</h2>
      </div>

      <div className={`${styles.field} ${styles.rowBetween}`}>
        <p className="textBody">Push notifications</p>
        <Switch checked={checked} onChange={toggle} disabled={disabled || saving} aria-label="Push notifications" />
      </div>
    </section>
  );
}
