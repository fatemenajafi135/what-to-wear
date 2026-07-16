import type { WardrobeItem } from "@/lib/types";

export function ClosetItemCard({ item }: { item: WardrobeItem }) {
  return (
    <div className="closet-item-card">
      <div className="closet-item-swatches">
        {(item.colors ?? []).map((hex) => (
          <span key={hex} className="closet-item-swatch" style={{ backgroundColor: hex }} title={hex} />
        ))}
      </div>
      <h3 className="closet-item-category">{item.category.replace("_", " ")}</h3>
      <dl className="closet-item-attrs">
        <div>
          <dt>Formality</dt>
          <dd>{item.formality.replace("_", " ")}</dd>
        </div>
        <div>
          <dt>Warmth</dt>
          <dd>{item.warmth}/5</dd>
        </div>
        <div>
          <dt>Season</dt>
          <dd>{(item.season ?? []).join(", ")}</dd>
        </div>
        {item.fabric && (
          <div>
            <dt>Fabric</dt>
            <dd>{item.fabric}</dd>
          </div>
        )}
        {item.pattern && (
          <div>
            <dt>Pattern</dt>
            <dd>{item.pattern}</dd>
          </div>
        )}
        {item.fit && (
          <div>
            <dt>Fit</dt>
            <dd>{item.fit}</dd>
          </div>
        )}
      </dl>
    </div>
  );
}
