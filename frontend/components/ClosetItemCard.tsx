import { useEffect, useState } from "react";

import { supabase } from "@/lib/supabase-client";
import type { WardrobeItem } from "@/lib/types";

export function ClosetItemCard({ item }: { item: WardrobeItem }) {
  const [photoUrl, setPhotoUrl] = useState<string | null>(null);

  useEffect(() => {
    if (!item.photo_path) {
      return;
    }
    let cancelled = false;
    supabase.storage
      .from("wardrobe-photos")
      .createSignedUrl(item.photo_path, 3600)
      .then(({ data, error }) => {
        if (!cancelled && !error && data?.signedUrl) {
          setPhotoUrl(data.signedUrl);
        }
      })
      .catch(() => {
        // swatch-only fallback, no thrown error (spec.md FR-006)
      });
    return () => {
      cancelled = true;
    };
  }, [item.photo_path]);

  return (
    <div className="card">
      {photoUrl && (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={photoUrl} alt={item.category.replace("_", " ")} className="closet-item-photo" />
      )}
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
