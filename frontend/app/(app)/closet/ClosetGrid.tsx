"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { TopHeader } from "@/components/ui/TopHeader/TopHeader";
import { Chip } from "@/components/ui/Chip/Chip";
import { Button } from "@/components/ui/Button/Button";
import { ItemPhoto } from "@/components/ui/ItemPhoto/ItemPhoto";
import { apiClient } from "@/lib/api/client";
import { useOnlineStatus } from "@/lib/useOnlineStatus";
import type { components } from "@/lib/api/schema";
import styles from "./ClosetGrid.module.css";

type ClosetItemView = components["schemas"]["ClosetItemView"];
type ChipFilter = "top" | "bottom" | "outerwear" | "footwear" | "accessory";

const CHIPS: { label: string; value: ChipFilter | null }[] = [
  { label: "All", value: null },
  { label: "Tops", value: "top" },
  { label: "Bottoms", value: "bottom" },
  { label: "Outerwear", value: "outerwear" },
  { label: "Shoes", value: "footwear" },
  { label: "Accessories", value: "accessory" },
];

interface ClosetGridProps {
  /** Highlights the currently-open item's tile in the desktop two-pane layout. */
  selectedItemId?: string;
}

/**
 * The Closet grid: header, category filter row, and every collection state
 * (design/design-system.md §6) — loading skeleton, first-run empty,
 * empty-filtered, error, and offline (suppressing its own error in favor of
 * the global banner, §6's precedence rule). Shared between `/closet` and
 * `/closet/[itemId]` (the latter renders it only at the ≥1024px two-pane
 * layout) so there is exactly one implementation of this state machine.
 */
export function ClosetGrid({ selectedItemId }: ClosetGridProps) {
  const [category, setCategory] = useState<ChipFilter | null>(null);
  const [items, setItems] = useState<ClosetItemView[]>([]);
  const [total, setTotal] = useState<number | null>(null);
  const [hasMore, setHasMore] = useState(false);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState(false);
  const isOnline = useOnlineStatus();

  // Discards a stale in-flight request's result if the filter changes again
  // before it resolves (spec.md edge case: no stale-data flash).
  const requestId = useRef(0);

  const load = useCallback(async (nextCategory: ChipFilter | null) => {
    const thisRequest = ++requestId.current;
    setLoading(true);
    setError(false);
    try {
      const { data, error: fetchError } = await apiClient.GET("/api/v1/closet/items", {
        params: { query: { category: nextCategory ?? undefined, offset: 0 } },
      });
      if (thisRequest !== requestId.current) return;
      if (fetchError || !data) {
        setError(true);
        return;
      }
      setItems(data.items);
      setTotal(data.total);
      setHasMore(data.has_more);
      setOffset(data.items.length);
    } catch {
      // A dropped connection rejects the fetch promise outright (distinct
      // from a non-2xx response, which openapi-fetch returns as `error`
      // above) — most commonly hit while offline, where this resolves to
      // the same suppressed-error state `showError` already handles.
      if (thisRequest === requestId.current) setError(true);
    } finally {
      if (thisRequest === requestId.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    load(category);
  }, [category, load]);

  const loadMore = async () => {
    setLoadingMore(true);
    try {
      const { data, error: fetchError } = await apiClient.GET("/api/v1/closet/items", {
        params: { query: { category: category ?? undefined, offset } },
      });
      if (fetchError || !data) return;
      setItems((prev) => [...prev, ...data.items]);
      setHasMore(data.has_more);
      setOffset((prev) => prev + data.items.length);
    } catch {
      // Offline/dropped connection — "Load more" simply stays available to
      // retry; no dedicated error state exists for this secondary action.
    } finally {
      setLoadingMore(false);
    }
  };

  const subtitle = total === null ? undefined : `${total} item${total === 1 ? "" : "s"}`;
  const showError = error && isOnline; // offline suppresses the screen-level error (design-system §6)

  return (
    <>
      <div className={styles.stickyHeader}>
        <TopHeader title="Closet" subtitle={subtitle} />
        <div className={styles.chipRow}>
          {CHIPS.map((chip) => (
            <Chip key={chip.label} active={category === chip.value} onClick={() => setCategory(chip.value)}>
              {chip.label}
            </Chip>
          ))}
        </div>
      </div>

      {loading && (
        // design-system.md § Per-screen skeleton layouts: always a fixed
        // 2×2 grid regardless of breakpoint — it doesn't follow the real
        // grid's responsive column count.
        <div className={styles.skeletonGrid} aria-hidden="true">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className={`${styles.tile} skeleton`} />
          ))}
        </div>
      )}

      {!loading && showError && (
        <div className={styles.stateBlock}>
          <p className={`textBody ${styles.stateBody}`}>Couldn&apos;t load your closet.</p>
          <Button width="intrinsic" onClick={() => load(category)}>
            Retry
          </Button>
        </div>
      )}

      {!loading && !error && total === 0 && category === null && (
        <div className={styles.stateBlock}>
          <p className={`textBody ${styles.stateBody}`}>
            Your closet is empty. Add a few pieces and I&apos;ll start suggesting outfits.
          </p>
          <Button href="/add" width="intrinsic">
            Add your first item
          </Button>
        </div>
      )}

      {!loading && !error && total === 0 && category !== null && (
        <div className={styles.stateBlock}>
          <p className={`textBody ${styles.stateBody}`}>No items match this filter.</p>
          <Button width="intrinsic" onClick={() => setCategory(null)}>
            Clear filter
          </Button>
        </div>
      )}

      {!loading && !error && total !== null && total > 0 && (
        <>
          <div className={styles.grid}>
            {items.map((item) => (
              <Link
                key={item.id}
                href={`/closet/${item.id}`}
                className={[styles.tile, item.id === selectedItemId && styles.tileSelected].filter(Boolean).join(" ")}
                aria-label={item.name ?? item.category}
              >
                <ItemPhoto
                  src={item.photo_url}
                  backgroundColor={item.photo_background_color}
                  className={styles.tilePhoto}
                />
              </Link>
            ))}
          </div>
          {hasMore && (
            <div className={styles.loadMore}>
              {loadingMore ? (
                <p className="textCaption">Loading more items…</p>
              ) : (
                <button type="button" className={styles.loadMoreButton} onClick={loadMore}>
                  Load more
                </button>
              )}
            </div>
          )}
        </>
      )}
    </>
  );
}
