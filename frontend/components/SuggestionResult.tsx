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
          <div className="card-kicker">Outfit {i + 1}</div>
          <ul className="outfit-items">
            {outfit.items.map((itemId) => {
              const item = closetById.get(itemId);
              return (
                <li key={itemId}>
                  {item ? (
                    <>
                      <span className="tag tag-accent">{item.category.replace("_", " ")}</span>{" "}
                      <span className="text-muted">({(item.colors ?? []).join(", ")})</span>
                    </>
                  ) : (
                    itemId
                  )}
                </li>
              );
            })}
          </ul>
          <div className="card-body">
            {outfit.rationale.map((r, j) => (
              <p key={j}>{r.text}</p>
            ))}
          </div>
        </div>
      ))}
      <details className="suggestion-raw">
        <summary className="text-muted">Full details</summary>
        <pre>{rendered}</pre>
      </details>
    </div>
  );
}
