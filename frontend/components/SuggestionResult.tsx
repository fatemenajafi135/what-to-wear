import type { OutfitResult, WardrobeItem } from "@/lib/types";

export function SuggestionResult({
  result,
  rendered,
  closetById,
}: {
  result: OutfitResult;
  rendered: string;
  closetById: Map<string, WardrobeItem>;
}) {
  if (result.outfits.length === 0) {
    // SC-006: a clear explanation, never a raw error or a fabricated outfit.
    return (
      <div className="suggestion-empty">
        <p>Your closet doesn&apos;t have enough to put together an outfit for that request yet.</p>
        <p>Try adding a few more items, or describe a different occasion.</p>
      </div>
    );
  }

  return (
    <div className="suggestion-results">
      {result.outfits.map((outfit, i) => (
        <div className="outfit-card" key={i}>
          <h3>Outfit {i + 1}</h3>
          <ul className="outfit-items">
            {outfit.items.map((itemId) => {
              const item = closetById.get(itemId);
              return (
                <li key={itemId}>
                  {item ? `${item.category.replace("_", " ")} (${(item.colors ?? []).join(", ")})` : itemId}
                </li>
              );
            })}
          </ul>
          <div className="outfit-rationale">
            {outfit.rationale.map((r, j) => (
              <p key={j}>{r.text}</p>
            ))}
          </div>
        </div>
      ))}
      <details className="suggestion-raw">
        <summary>Full details</summary>
        <pre>{rendered}</pre>
      </details>
    </div>
  );
}
