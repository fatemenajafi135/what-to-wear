"use client";

import { useState } from "react";
import { SegmentedControl } from "@/components/ui/SegmentedControl/SegmentedControl";
import { getStoredTheme, setStoredTheme, type ThemePreference } from "@/lib/theme";
import styles from "./sections.module.css";

const OPTIONS: { value: ThemePreference; label: string }[] = [
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark" },
  { value: "system", label: "System" },
];

/**
 * issue #26. Purely a local/device preference (localStorage, not the
 * backend profile) — no Edit/Done, commits immediately like Notifications.
 * Default is Light, applied at boot by a blocking script (app/layout.tsx)
 * reading the same storage key this section writes to (lib/theme.ts).
 */
export function AppearanceSection() {
  const [theme, setTheme] = useState<ThemePreference>(() => getStoredTheme());

  function select(value: string) {
    const next = value as ThemePreference;
    setTheme(next);
    setStoredTheme(next);
  }

  return (
    <section>
      <div className={styles.header}>
        <h2 className="textSectionTitle">Appearance</h2>
      </div>

      <div className={styles.field}>
        <p className={`textLabel ${styles.fieldLabel}`}>Theme</p>
        <SegmentedControl options={OPTIONS} value={theme} onChange={select} />
      </div>
    </section>
  );
}
