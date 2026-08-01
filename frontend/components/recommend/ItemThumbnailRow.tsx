import Link from "next/link";
import { NoPhoto } from "@/components/ui/NoPhoto/NoPhoto";
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
          {item.photo_url ? (
            // eslint-disable-next-line @next/next/no-img-element -- a signed Storage URL, not a static/optimizable asset
            <img src={item.photo_url} alt="" className={styles.photo} />
          ) : (
            <NoPhoto className={styles.photo} />
          )}
        </Link>
      ))}
    </div>
  );
}
