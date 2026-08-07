import type { components } from "@/lib/api/schema";
import styles from "./MatchBreakdown.module.css";

type DimensionScoreView = components["schemas"]["DimensionScoreView"];
type MatchLabel = components["schemas"]["OutfitDetailResponse"]["match_label"];

const MATCH_LABEL_TEXT: Record<MatchLabel, string> = {
  great: "Great match",
  good: "Good match",
  might_work: "Might work",
};

// design-system.md's own "Open questions" flags the exact per-dimension
// label text as undecided ("what's the exact display label text for
// each?") — explicitly a decide-during-build gap, not a hard spec value.
const DIMENSION_LABELS: Record<string, string> = {
  color_harmony: "Color harmony",
  formality_coherence: "Formality",
  weather_fitness: "Weather fit",
  silhouette_balance: "Silhouette",
};

export interface MatchBreakdownProps {
  matchLabel: MatchLabel;
  dimensionScores: DimensionScoreView[];
}

/**
 * design/design-system.md § Outfit detail item 2(d) / § Scores: a
 * "Match level: {label}" row using the same pill treatment as the chat/
 * gallery cards, then one bar per dimension (`--color-primary` fill,
 * `--color-surface-sunken` track). `value` only ever drives a CSS width —
 * it is never interpolated into any text node on this page (Constitution
 * II / FR-004 / SC-003).
 */
export function MatchBreakdown({ matchLabel, dimensionScores }: MatchBreakdownProps) {
  return (
    <div className={styles.wrapper}>
      <div className={styles.levelRow}>
        <span className="textCaption">Match level:</span>
        <span className={styles.pill}>{MATCH_LABEL_TEXT[matchLabel]}</span>
      </div>
      {dimensionScores.map((score) => (
        <div key={score.dimension} className={styles.bar}>
          <span className={styles.barLabel}>{DIMENSION_LABELS[score.dimension] ?? score.dimension}</span>
          <span className={styles.track}>
            <span className={styles.fill} style={{ width: `${Math.max(0, Math.min(1, score.value)) * 100}%` }} />
          </span>
        </div>
      ))}
    </div>
  );
}
