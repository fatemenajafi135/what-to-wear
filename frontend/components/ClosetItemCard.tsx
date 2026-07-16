import type { WardrobeItem } from "@/lib/types";

export function ClosetItemCard({ item }: { item: WardrobeItem }) {
  return (
    <div className="card">
      <div className="closet-item-swatches">
        {(item.colors ?? []).map((hex) => (
          <span key={hex} className="closet-item-swatch" style={{ backgroundColor: hex }} title={hex} />
        ))}
      </div>
      <div className="card-title">{item.category.replace("_", " ")}</div>
      <div className="closet-item-attrs">
        <div>
          <span>Formality</span>
          <span>{item.formality.replace("_", " ")}</span>
        </div>
        <div>
          <span>Warmth</span>
          <span>{item.warmth}/5</span>
        </div>
        <div>
          <span>Season</span>
          <span>{(item.season ?? []).join(", ")}</span>
        </div>
      </div>
      <div className="tag-toggle-group">
        {item.fabric && <span className="tag tag-neutral">{item.fabric}</span>}
        {item.pattern && <span className="tag tag-neutral">{item.pattern}</span>}
        {item.fit && <span className="tag tag-neutral">{item.fit}</span>}
      </div>
    </div>
  );
}
