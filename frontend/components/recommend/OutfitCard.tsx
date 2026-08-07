import { IconButton } from "@/components/ui/IconButton/IconButton";
import type { components } from "@/lib/api/schema";
import { ItemThumbnailRow } from "./ItemThumbnailRow";
import styles from "./OutfitCard.module.css";

type StylingOutfit = components["schemas"]["StylingOutfit"];

const MATCH_LABEL_TEXT: Record<StylingOutfit["match_label"], string> = {
  great: "Great match",
  good: "Good match",
  might_work: "Might work",
};

export interface OutfitCardProps {
  outfit: StylingOutfit;
  saved: boolean;
  feedback: "up" | "down" | null;
  onToggleHeart: () => void;
  onFeedback: (value: "up" | "down") => void;
  onCardTap: () => void;
}

/**
 * design/design-system.md § Outfit suggestion pager. Its own card variant,
 * distinct from the Outfits-gallery card. The description is plain text —
 * no citation Badges here, ever (§ Badge; design-decisions.md §33/§35).
 * The card body (outside the heart, thumbnails, and feedback controls) is
 * tappable → navigates to that outfit's real, already-saved Outfit detail
 * page (design-decisions.md §42 — every card here has a real id from the
 * moment it's generated, never a not-yet-saved placeholder).
 */
export function OutfitCard({ outfit, saved, feedback, onToggleHeart, onFeedback, onCardTap }: OutfitCardProps) {
  return (
    <div
      className={styles.card}
      onClick={onCardTap}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onCardTap();
        }
      }}
      role="button"
      tabIndex={0}
    >
      <div className={styles.header}>
        <span className={styles.title}>{outfit.occasion}</span>
        <span className={styles.pill}>{MATCH_LABEL_TEXT[outfit.match_label]}</span>
        <span className={styles.spacer} />
        <IconButton
          icon={saved ? "heartFilled" : "heart"}
          label={saved ? "Unsave outfit" : "Save outfit"}
          onClick={(e) => {
            e.stopPropagation();
            onToggleHeart();
          }}
        />
      </div>

      <p className={`textBody ${styles.description}`}>{outfit.rationale_text}</p>

      <ItemThumbnailRow items={outfit.items} />

      <p className={styles.metaLine}>{outfit.meta_line}</p>

      <div className={styles.footer}>
        <IconButton
          icon="thumbsDown"
          label="Not helpful"
          className={feedback === "down" ? styles.thumbDownActive : undefined}
          onClick={(e) => {
            e.stopPropagation();
            onFeedback("down");
          }}
        />
        <IconButton
          icon="thumbsUp"
          label="Helpful"
          className={feedback === "up" ? styles.thumbUpActive : undefined}
          onClick={(e) => {
            e.stopPropagation();
            onFeedback("up");
          }}
        />
      </div>
    </div>
  );
}
