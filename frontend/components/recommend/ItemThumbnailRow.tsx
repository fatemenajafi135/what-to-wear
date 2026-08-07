import Link from "next/link";
import { ItemPhoto } from "@/components/ui/ItemPhoto/ItemPhoto";
import type { components } from "@/lib/api/schema";
import styles from "./ItemThumbnailRow.module.css";

type RecommendItemView = components["schemas"]["RecommendItemView"];

export interface ItemThumbnailRowProps {
  items: RecommendItemView[];
}

/**
 * design/design-system.md § Screen anatomy → Recommend, item 3 / § Badge:
 * 56×56 thumbnails below an assistant reply, each tappable → Item detail.
 * The thumbnail, not a citation Badge, is the tappable/deep-linking element.
 */
export function ItemThumbnailRow({ items }: ItemThumbnailRowProps) {
  if (items.length === 0) return null;

  return (
    <div className={styles.row}>
      {items.map((item) => (
        <Link
          key={item.id}
          href={`/closet/${item.id}`}
          className={styles.thumb}
          aria-label={item.name ?? item.category}
        >
          <ItemPhoto
            src={item.photo_url}
            backgroundColor={item.photo_background_color}
            className={styles.photo}
            radius={8}
          />
        </Link>
      ))}
    </div>
  );
}
