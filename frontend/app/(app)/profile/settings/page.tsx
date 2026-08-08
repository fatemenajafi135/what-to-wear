"use client";

import { useEffect, useState } from "react";
import { TopHeader } from "@/components/ui/TopHeader/TopHeader";
import { Button } from "@/components/ui/Button/Button";
import { getProfile, type ProfileResponse } from "@/lib/api/profile";
import { useOnlineStatus } from "@/lib/useOnlineStatus";
import { StylePreferencesSection } from "./sections/StylePreferencesSection";
import { BodySizeSection } from "./sections/BodySizeSection";
import { AccountSection } from "./sections/AccountSection";
import { ConnectedAccountsSection } from "./sections/ConnectedAccountsSection";
import { NotificationsSection } from "./sections/NotificationsSection";
import { AppearanceSection } from "./sections/AppearanceSection";
import styles from "./page.module.css";

type SectionKey = "style" | "body" | "account" | "connected" | "notifications" | "appearance";

const SECTIONS: { key: SectionKey; label: string }[] = [
  { key: "style", label: "Style preferences" },
  { key: "body", label: "Body & size" },
  { key: "account", label: "Account" },
  { key: "connected", label: "Connected accounts" },
  { key: "notifications", label: "Notifications" },
  { key: "appearance", label: "Appearance" },
];

type LoadState = "loading" | "ready" | "error";

/**
 * design/design-system.md §4: one route, in-page sections, no sub-routes.
 * "Appearance" (issue #26) is a sixth section not in the design system —
 * a net-new control, not covered there. §5's two-pane rule: at 1024px+ a
 * fixed 320px section list sits
 * beside the detail pane; below that, the list and the active section's
 * detail are mutually exclusive views (mobileShowingList) — this repo has no
 * existing precedent for that split, since Settings was a static stub before
 * this feature.
 */
export default function SettingsPage() {
  const [loadState, setLoadState] = useState<LoadState>("loading");
  const [profile, setProfile] = useState<ProfileResponse | null>(null);
  const [activeSection, setActiveSection] = useState<SectionKey>("style");
  const [mobileShowingList, setMobileShowingList] = useState(true);
  const isOnline = useOnlineStatus();
  const isOffline = !isOnline;

  async function load() {
    setLoadState("loading");
    try {
      const result = await getProfile();
      setProfile(result);
      setLoadState("ready");
    } catch {
      setLoadState("error");
    }
  }

  useEffect(() => {
    load();
  }, []);

  function selectSection(key: SectionKey) {
    setActiveSection(key);
    setMobileShowingList(false);
  }

  const activeSectionLabel = SECTIONS.find((section) => section.key === activeSection)?.label ?? "";

  function renderSection(profile: ProfileResponse) {
    switch (activeSection) {
      case "style":
        return <StylePreferencesSection profile={profile} disabled={isOffline} onSaved={setProfile} />;
      case "body":
        return <BodySizeSection profile={profile} disabled={isOffline} onSaved={setProfile} />;
      case "account":
        return <AccountSection disabled={isOffline} />;
      case "connected":
        return <ConnectedAccountsSection />;
      case "notifications":
        return <NotificationsSection profile={profile} disabled={isOffline} onSaved={setProfile} />;
      case "appearance":
        return <AppearanceSection />;
    }
  }

  return (
    <>
      <div className={!mobileShowingList ? styles.hideBelowDesktop : undefined}>
        <TopHeader title="Settings" backHref="/profile" />
      </div>
      {!mobileShowingList && (
        <div className={styles.mobileDetailHeader}>
          <TopHeader title={activeSectionLabel} subtitle="Settings" onBack={() => setMobileShowingList(true)} />
        </div>
      )}

      {loadState === "loading" && (
        <div className={styles.skeletonStack}>
          <div className={`skeleton ${styles.skeletonBlockLg}`} />
          <div className={`skeleton ${styles.skeletonBlockLg}`} />
          <div className={`skeleton ${styles.skeletonBlockSm}`} />
        </div>
      )}

      {loadState === "error" && !isOffline && (
        <div className={styles.errorBanner}>
          <p className="textBody">That didn&apos;t save. Check your connection and try again.</p>
          <Button variant="outline" width="intrinsic" onClick={load}>
            Retry
          </Button>
        </div>
      )}

      {loadState === "ready" && profile && (
        <div className={styles.layout}>
          <div className={`${styles.listPane} ${!mobileShowingList ? styles.hideBelowDesktop : ""}`}>
            <ul className={styles.sectionList}>
              {SECTIONS.map((section) => (
                <li key={section.key}>
                  <button
                    type="button"
                    className={[
                      "textBody",
                      styles.sectionRow,
                      activeSection === section.key ? styles.sectionRowActive : "",
                    ].join(" ")}
                    aria-current={activeSection === section.key ? "page" : undefined}
                    onClick={() => selectSection(section.key)}
                  >
                    {section.label}
                  </button>
                </li>
              ))}
            </ul>
          </div>

          <div className={`${styles.detailPane} ${mobileShowingList ? styles.hideBelowDesktop : ""}`}>
            {renderSection(profile)}
          </div>
        </div>
      )}
    </>
  );
}
