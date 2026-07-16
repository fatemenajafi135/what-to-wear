import { useSignedPhotoUrl } from "@/lib/use-signed-photo-url";
import type { WardrobeItem } from "@/lib/types";

/** One item within an outfit-suggestion row. Reuses the same signed-URL
 * mechanism as ClosetItemCard (Feature 006) -- when a photo resolves, show
 * it; otherwise (no photo_path, expired/missing object, network error) fall
 * back to the same text/color presentation the outfit list used before this
 * feature, never a broken <img> (spec.md FR-008). */
export function OutfitItemPhoto({ item }: { item: WardrobeItem }) {
  const photoUrl = useSignedPhotoUrl(item.photo_path);

  return (
    <div className="outfit-item-photo">
      {photoUrl ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={photoUrl} alt={item.category.replace("_", " ")} className="outfit-item-photo-img" />
      ) : (
        <div className="outfit-item-photo-swatches">
          {(item.colors ?? []).map((hex) => (
            <span key={hex} className="closet-item-swatch" style={{ backgroundColor: hex }} title={hex} />
          ))}
        </div>
      )}
      <span className="tag tag-accent">{item.category.replace("_", " ")}</span>
      <span className="text-muted" style={{ fontSize: 11 }}>
        {(item.colors ?? []).join(", ")}
      </span>
    </div>
  );
}
