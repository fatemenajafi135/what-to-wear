"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { TopHeader } from "@/components/ui/TopHeader/TopHeader";
import { IconButton } from "@/components/ui/IconButton/IconButton";
import { ItemPhoto } from "@/components/ui/ItemPhoto/ItemPhoto";
import { Button } from "@/components/ui/Button/Button";
import { apiClient } from "@/lib/api/client";
import { useOnlineStatus } from "@/lib/useOnlineStatus";
import type { components } from "@/lib/api/schema";
import { OutfitOverflowSheet } from "./OutfitOverflowSheet";
import { DeleteOutfitDialog } from "./DeleteOutfitDialog";
import { SortSheet, SortSheetTrigger, type OutfitSort } from "./SortSheet";
import styles from "./OutfitsGrid.module.css";

type OutfitSummary = components["schemas"]["OutfitSummary"];

const MATCH_LABEL_TEXT: Record<OutfitSummary["match_label"], string> = {
  great: "Great match",
  good: "Good match",
  might_work: "Might work",
};

function formatOutfitDate(iso: string): string {
  const date = new Date(iso);
  const now = new Date();
  if (date.toDateString() === now.toDateString()) return "Today";
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

interface OutfitsGridProps {
  /** Highlights the currently-open outfit's card in the desktop two-pane layout. */
  selectedOutfitId?: string;
}

/**
 * The Outfits gallery: header, "Filter & sort" trigger (sort-only this
 * feature — design-decisions.md §41), and every collection state
 * (loading/first-run-empty/error/offline). Shared between `/outfits` and
 * `/outfits/[outfitId]` (the latter renders it only at the ≥1024px
 * two-pane layout), mirroring `ClosetGrid.tsx`'s composition exactly.
 */
export function OutfitsGrid({ selectedOutfitId }: OutfitsGridProps) {
  const router = useRouter();
  const [outfits, setOutfits] = useState<OutfitSummary[]>([]);
  const [total, setTotal] = useState<number | null>(null);
  const [hasMore, setHasMore] = useState(false);
  const [offset, setOffset] = useState(0);
  const [sort, setSort] = useState<OutfitSort>("date");
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState(false);
  const [sortSheetOpen, setSortSheetOpen] = useState(false);
  const [menuOpenFor, setMenuOpenFor] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<OutfitSummary | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draftTitle, setDraftTitle] = useState("");
  const isOnline = useOnlineStatus();

  const requestId = useRef(0);

  const load = useCallback(async (nextSort: OutfitSort) => {
    const thisRequest = ++requestId.current;
    setLoading(true);
    setError(false);
    try {
      const { data, error: fetchError } = await apiClient.GET("/api/v1/recommend/outfits", {
        params: { query: { sort: nextSort, offset: 0 } },
      });
      if (thisRequest !== requestId.current) return;
      if (fetchError || !data) {
        setError(true);
        return;
      }
      setOutfits(data.outfits);
      setTotal(data.total);
      setHasMore(data.has_more);
      setOffset(data.outfits.length);
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
    load(sort);
  }, [sort, load]);

  const loadMore = async () => {
    setLoadingMore(true);
    try {
      const { data, error: fetchError } = await apiClient.GET("/api/v1/recommend/outfits", {
        params: { query: { sort, offset } },
      });
      if (fetchError || !data) return;
      setOutfits((prev) => [...prev, ...data.outfits]);
      setHasMore(data.has_more);
      setOffset((prev) => prev + data.outfits.length);
    } catch {
      // Offline/dropped connection — "Load more" simply stays available to
      // retry; no dedicated error state exists for this secondary action.
    } finally {
      setLoadingMore(false);
    }
  };

  const showError = error && isOnline; // offline suppresses the screen-level error (design-system §6)

  async function handleToggleFavorite(outfit: OutfitSummary) {
    const { data } = await apiClient.POST("/api/v1/recommend/outfits/{outfit_id}/favorite", {
      params: { path: { outfit_id: outfit.id } },
    });
    if (data) {
      setOutfits((prev) => prev.map((o) => (o.id === outfit.id ? { ...o, favorite: data.favorite } : o)));
    }
  }

  function startEditing(outfit: OutfitSummary) {
    setEditingId(outfit.id);
    setDraftTitle(outfit.title);
  }

  async function commitRename(outfitId: string) {
    const title = draftTitle.trim();
    setEditingId(null);
    if (!title) return;
    const { data } = await apiClient.PATCH("/api/v1/recommend/outfits/{outfit_id}/title", {
      params: { path: { outfit_id: outfitId } },
      body: { title },
    });
    if (data) {
      setOutfits((prev) => prev.map((o) => (o.id === outfitId ? { ...o, title: data.title } : o)));
    }
  }

  async function handleLogWorn(outfitId: string) {
    await apiClient.POST("/api/v1/recommend/outfits/{outfit_id}/wear", {
      params: { path: { outfit_id: outfitId } },
    });
  }

  async function handleDeleteConfirmed() {
    if (!deleteTarget) return;
    const outfitId = deleteTarget.id;
    setDeleteTarget(null);
    const { response } = await apiClient.DELETE("/api/v1/recommend/outfits/{outfit_id}", {
      params: { path: { outfit_id: outfitId } },
    });
    if (response.ok) {
      setOutfits((prev) => prev.filter((o) => o.id !== outfitId));
      setTotal((prev) => (prev !== null ? prev - 1 : prev));
      if (selectedOutfitId === outfitId) router.push("/outfits");
    }
  }

  return (
    <>
      <div className={styles.stickyHeader}>
        <TopHeader title="Outfits" subtitle={total === null ? undefined : `${total} outfit${total === 1 ? "" : "s"}`} />
        <div className={styles.toolbar}>
          <SortSheetTrigger onOpen={() => setSortSheetOpen(true)} />
        </div>
      </div>
      <SortSheet open={sortSheetOpen} onClose={() => setSortSheetOpen(false)} sort={sort} onChange={setSort} />

      {loading && (
        // design-system.md § Per-screen skeleton layouts: two 100px-tall
        // blocks at 16px radius, approximating two collapsed outfit cards.
        <div className={styles.skeletonList} aria-hidden="true">
          <div className={`${styles.skeletonCard} skeleton`} />
          <div className={`${styles.skeletonCard} skeleton`} />
        </div>
      )}

      {!loading && showError && (
        <div className={styles.stateBlock}>
          <p className={`textBody ${styles.stateBody}`}>Couldn&apos;t load your outfits.</p>
          <Button width="intrinsic" onClick={() => load(sort)}>
            Retry
          </Button>
        </div>
      )}

      {!loading && !error && outfits.length === 0 && (
        <div className={styles.stateBlock}>
          <p className={`textBody ${styles.stateBody}`}>
            No outfits yet. Ask me to style something and I&apos;ll save the looks here.
          </p>
          <Button href="/recommend" width="intrinsic">
            Go to Styling
          </Button>
        </div>
      )}

      {!loading && !error && outfits.length > 0 && (
        <>
          <div className={styles.list}>
            {outfits.map((outfit) => {
              const extra = outfit.item_count - 3;
              const visibleThumbnails =
                outfit.item_count > 4 ? outfit.item_thumbnails.slice(0, 3) : outfit.item_thumbnails;

              return (
                <div
                  key={outfit.id}
                  className={[styles.card, outfit.id === selectedOutfitId && styles.cardSelected]
                    .filter(Boolean)
                    .join(" ")}
                >
                  <div className={styles.header}>
                    {editingId === outfit.id ? (
                      <>
                        <input
                          className={styles.titleInput}
                          value={draftTitle}
                          onChange={(e) => setDraftTitle(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") commitRename(outfit.id);
                            if (e.key === "Escape") setEditingId(null);
                          }}
                          ref={(el) => el?.focus()}
                          aria-label="Outfit title"
                        />
                        <button
                          type="button"
                          className={`control ${styles.doneButton}`}
                          onClick={() => commitRename(outfit.id)}
                        >
                          Done
                        </button>
                      </>
                    ) : (
                      <button type="button" className={styles.titleButton} onClick={() => startEditing(outfit)}>
                        {outfit.title}
                      </button>
                    )}
                    <span className={styles.pill}>{MATCH_LABEL_TEXT[outfit.match_label]}</span>
                    <span className={styles.spacer} />
                    <IconButton
                      icon={outfit.favorite ? "heartFilled" : "heart"}
                      label={outfit.favorite ? "Unsave outfit" : "Save outfit"}
                      disabled={!isOnline}
                      onClick={() => handleToggleFavorite(outfit)}
                    />
                    <IconButton icon="dots" label="More options" onClick={() => setMenuOpenFor(outfit.id)} />
                  </div>
                  <p className={styles.date}>{formatOutfitDate(outfit.created_at)}</p>

                  <div className={styles.itemRow}>
                    {visibleThumbnails.map((item) => (
                      <Link key={item.id} href={`/closet/${item.id}`} className={styles.thumb}>
                        <ItemPhoto
                          src={item.photo_url}
                          backgroundColor={item.photo_background_color}
                          className={styles.thumbPhoto}
                          radius={8}
                        />
                      </Link>
                    ))}
                    {outfit.item_count > 4 && (
                      <Link href={`/outfits/${outfit.id}`} className={`${styles.thumb} ${styles.overflowChip}`}>
                        +{extra}
                      </Link>
                    )}
                  </div>

                  <Link
                    href={`/outfits/${outfit.id}`}
                    className={styles.cardLink}
                    aria-label={`Open ${outfit.title}`}
                  />

                  <OutfitOverflowSheet
                    open={menuOpenFor === outfit.id}
                    onClose={() => setMenuOpenFor(null)}
                    isOnline={isOnline}
                    onLogWorn={() => handleLogWorn(outfit.id)}
                    onEditTitle={() => startEditing(outfit)}
                    onDelete={() => setDeleteTarget(outfit)}
                  />
                </div>
              );
            })}
          </div>
          {hasMore && (
            <div className={styles.loadMore}>
              {loadingMore ? (
                <p className="textCaption">Loading more outfits…</p>
              ) : (
                <button type="button" className={styles.loadMoreButton} onClick={loadMore}>
                  Load more
                </button>
              )}
            </div>
          )}
        </>
      )}

      <DeleteOutfitDialog
        open={deleteTarget !== null}
        outfitTitle={deleteTarget?.title ?? "this outfit"}
        onConfirm={handleDeleteConfirmed}
        onCancel={() => setDeleteTarget(null)}
      />
    </>
  );
}
