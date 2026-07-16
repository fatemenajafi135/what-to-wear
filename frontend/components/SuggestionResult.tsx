import type { SuggestResult, WardrobeItem } from "@/lib/types";
import { OutfitReaction } from "@/components/OutfitReaction";
import { OutfitItemPhoto } from "@/components/OutfitItemPhoto";

const DIMENSION_LABELS: Record<string, string> = {
  color_harmony: "Color harmony",
  formality_coherence: "Formality",
  weather_fitness: "Weather fit",
  silhouette_balance: "Silhouette",
};

export function SuggestionResult({
  result,
  closetById,
}: {
  result: SuggestResult;
  closetById: Map<string, WardrobeItem>;
}) {
  if (result.outfits.length === 0) {
    // SC-006: a clear explanation, never a raw error or a fabricated outfit.
    return (
      <div className="card">
        <p>Your closet doesn&apos;t have enough to put together an outfit for that request yet.</p>
        <p className="text-muted">Try adding a few more items, or describe a different occasion.</p>
      </div>
    );
  }

  return (
    <div className="suggestion-results">
      {result.outfits.map((outfit, i) => (
        <div className="outfit-card card" key={i}>
          <div className="card-kicker">
            Outfit {i + 1} <span className="text-muted">— score {outfit.rank_score.toFixed(2)}</span>
          </div>
          <div className="outfit-item-photos">
            {outfit.items.map((itemId) => {
              const item = closetById.get(itemId);
              return item ? <OutfitItemPhoto key={itemId} item={item} /> : <span key={itemId}>{itemId}</span>;
            })}
          </div>
          <div className="card-body">
            {outfit.rationale.map((r, j) => (
              <p key={j}>{r.text}</p>
            ))}
          </div>
          <ul className="outfit-scores">
            {outfit.scores.map((s) => (
              <li key={s.dimension} title={s.reason}>
                <span className="text-muted">{DIMENSION_LABELS[s.dimension] ?? s.dimension}</span>{" "}
                <span className="tag">{s.value.toFixed(2)}</span>
              </li>
            ))}
          </ul>
          <OutfitReaction itemIds={outfit.items} />
        </div>
      ))}
    </div>
  );
}
