import type { PreferenceProfile } from "@/lib/types";

/** Presentational: renders a derived PreferenceProfile (US3) plus the
 * remove-one/clear-all actions (US4). Data fetching and the actions'
 * network calls live in the page component, matching how
 * ClosetPage/ClosetItemCard split responsibilities. */
export function PreferencesView({
  profile,
  onRemoveSignal,
  onClearAll,
  busy,
}: {
  profile: PreferenceProfile;
  onRemoveSignal: (key: string) => void;
  onClearAll: () => void;
  busy: boolean;
}) {
  if (!profile.has_feedback) {
    // FR-008: a clear "nothing learned yet" state, never an error or blank screen.
    return (
      <div className="card">
        <p className="text-muted">
          Nothing learned yet — react to a few suggestions and your preferences will show up here.
        </p>
      </div>
    );
  }

  const signals = profile.signals ?? [];

  if (signals.length === 0) {
    return (
      <div className="card">
        <p className="text-muted">
          You&apos;ve given some feedback, but no clear pattern has emerged yet — keep reacting to suggestions.
        </p>
      </div>
    );
  }

  return (
    <div className="preferences-view">
      <ul className="preferences-signal-list">
        {signals.map((signal) => (
          <li key={signal.key} className="card preferences-signal">
            <span>{signal.summary}</span>
            <button
              type="button"
              className="btn btn-ghost"
              disabled={busy}
              onClick={() => onRemoveSignal(signal.key)}
            >
              Remove
            </button>
          </li>
        ))}
      </ul>
      <button type="button" className="btn btn-secondary" disabled={busy} onClick={onClearAll}>
        Clear all preferences
      </button>
    </div>
  );
}
