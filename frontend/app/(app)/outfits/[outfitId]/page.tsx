"use client";

import { use, useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { TopHeader } from "@/components/ui/TopHeader/TopHeader";
import { IconButton } from "@/components/ui/IconButton/IconButton";
import { Button } from "@/components/ui/Button/Button";
import { ItemPhoto } from "@/components/ui/ItemPhoto/ItemPhoto";
import { apiClient } from "@/lib/api/client";
import { useOnlineStatus } from "@/lib/useOnlineStatus";
import type { components } from "@/lib/api/schema";
import { OutfitsGrid } from "../OutfitsGrid";
import { OutfitOverflowSheet } from "../OutfitOverflowSheet";
import { DeleteOutfitDialog } from "../DeleteOutfitDialog";
import { RationaleWithCitations } from "./RationaleWithCitations";
import { CitedRuleList } from "./CitedRuleList";
import { MatchBreakdown } from "./MatchBreakdown";
import twoPaneStyles from "../page.module.css";
import styles from "./page.module.css";

type OutfitDetailResponse = components["schemas"]["OutfitDetailResponse"];

/**
 * `/outfits/:outfitId` — design/design-system.md § Outfit detail: header
 * with back + favorite heart + overflow (dots), the item grid (deliberately
 * large tiles), the cited description, the rules list, and the Match
 * breakdown. At ≥1024px (design-system.md §5's two-pane master-detail),
 * the outfits list renders in a pane to the left, mirroring
 * `/closet/[itemId]/page.tsx`'s own two-pane composition.
 */
export default function OutfitDetailPage({ params }: { params: Promise<{ outfitId: string }> }) {
  const { outfitId } = use(params);
  const router = useRouter();
  const [outfit, setOutfit] = useState<OutfitDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState(false);
  const [sheetOpen, setSheetOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [editing, setEditing] = useState(false);
  const [draftTitle, setDraftTitle] = useState("");
  const isOnline = useOnlineStatus();

  const load = useCallback(async () => {
    setLoading(true);
    setNotFound(false);
    setError(false);
    try {
      const { data, response } = await apiClient.GET("/api/v1/recommend/outfits/{outfit_id}", {
        params: { path: { outfit_id: outfitId } },
      });
      if (response.status === 404) {
        setNotFound(true);
        return;
      }
      if (!data) {
        setError(true);
        return;
      }
      setOutfit(data);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, [outfitId]);

  useEffect(() => {
    load();
  }, [load]);

  const showError = error && isOnline; // offline suppresses the screen-level error (design-system §6)

  const handleToggleFavorite = async () => {
    const { data } = await apiClient.POST("/api/v1/recommend/outfits/{outfit_id}/favorite", {
      params: { path: { outfit_id: outfitId } },
    });
    if (data) setOutfit((prev) => (prev ? { ...prev, favorite: data.favorite } : prev));
  };

  const handleLogWorn = async () => {
    await apiClient.POST("/api/v1/recommend/outfits/{outfit_id}/wear", {
      params: { path: { outfit_id: outfitId } },
    });
  };

  const startEditing = () => {
    if (!outfit) return;
    setDraftTitle(outfit.title);
    setEditing(true);
  };

  const commitRename = async () => {
    const title = draftTitle.trim();
    setEditing(false);
    if (!title) return;
    const { data } = await apiClient.PATCH("/api/v1/recommend/outfits/{outfit_id}/title", {
      params: { path: { outfit_id: outfitId } },
      body: { title },
    });
    if (data) setOutfit((prev) => (prev ? { ...prev, title: data.title } : prev));
  };

  const handleDeleteConfirmed = async () => {
    setDeleteDialogOpen(false);
    const { response } = await apiClient.DELETE("/api/v1/recommend/outfits/{outfit_id}", {
      params: { path: { outfit_id: outfitId } },
    });
    if (response.ok) {
      router.push("/outfits");
    }
  };

  return (
    <div className={twoPaneStyles.twoPane}>
      <div className={twoPaneStyles.gridPane}>
        <OutfitsGrid selectedOutfitId={outfitId} />
      </div>

      <div>
        {editing && outfit ? (
          <div className={styles.editHeader}>
            <input
              className={styles.titleInput}
              value={draftTitle}
              onChange={(e) => setDraftTitle(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") commitRename();
                if (e.key === "Escape") setEditing(false);
              }}
              ref={(el) => el?.focus()}
              aria-label="Outfit title"
            />
            <button type="button" className={`control ${styles.doneButton}`} onClick={commitRename}>
              Done
            </button>
          </div>
        ) : (
          <TopHeader
            title={outfit?.title ?? "Outfit detail"}
            subtitle={
              outfit ? new Date(outfit.created_at).toLocaleDateString(undefined, { dateStyle: "medium" }) : undefined
            }
            backHref="/outfits"
            rightSlot={
              outfit
                ? {
                    kind: "custom",
                    node: (
                      <div className={styles.headerActions}>
                        <IconButton
                          icon={outfit.favorite ? "heartFilled" : "heart"}
                          label={outfit.favorite ? "Unsave outfit" : "Save outfit"}
                          disabled={!isOnline}
                          onClick={handleToggleFavorite}
                        />
                        <IconButton icon="dots" label="More options" onClick={() => setSheetOpen(true)} />
                      </div>
                    ),
                  }
                : { kind: "none" }
            }
          />
        )}

        {loading && (
          // design-system.md § Per-screen skeleton layouts: a 2-column
          // item-thumbnail grid then a description-shaped bar.
          <div className={styles.wrapper} aria-hidden="true">
            <div className={styles.skeletonGrid}>
              <div className={`${styles.skeletonTile} skeleton`} />
              <div className={`${styles.skeletonTile} skeleton`} />
            </div>
            <div className={`${styles.skeletonDescription} skeleton`} />
          </div>
        )}

        {!loading && notFound && (
          <div className={styles.stateBlock}>
            <p className={`textBody ${styles.stateBody}`}>
              This outfit couldn&apos;t be found — it may have been removed.
            </p>
            <Button href="/outfits" width="intrinsic">
              Back to Outfits
            </Button>
          </div>
        )}

        {!loading && showError && (
          <div className={styles.stateBlock}>
            <p className={`textBody ${styles.stateBody}`}>Couldn&apos;t load your outfits.</p>
            <Button width="intrinsic" onClick={load}>
              Retry
            </Button>
          </div>
        )}

        {!loading && !notFound && !error && outfit && (
          <div className={styles.wrapper}>
            <div className={styles.card}>
              <div className={styles.itemGrid}>
                {outfit.items.map((item) => (
                  <ItemPhoto
                    key={item.id}
                    src={item.photo_url}
                    backgroundColor={item.photo_background_color}
                    className={styles.itemTile}
                    radius={14}
                  />
                ))}
              </div>

              <div className={styles.description}>
                <RationaleWithCitations
                  rationaleText={outfit.rationale_text}
                  rationaleWithCitations={outfit.rationale_with_citations}
                />
              </div>

              <CitedRuleList citations={outfit.citations} />

              <MatchBreakdown matchLabel={outfit.match_label} dimensionScores={outfit.dimension_scores} />
            </div>
          </div>
        )}

        {outfit && (
          <>
            <OutfitOverflowSheet
              open={sheetOpen}
              onClose={() => setSheetOpen(false)}
              isOnline={isOnline}
              onLogWorn={handleLogWorn}
              onEditTitle={startEditing}
              onDelete={() => setDeleteDialogOpen(true)}
            />
            <DeleteOutfitDialog
              open={deleteDialogOpen}
              outfitTitle={outfit.title}
              onConfirm={handleDeleteConfirmed}
              onCancel={() => setDeleteDialogOpen(false)}
            />
          </>
        )}
      </div>
    </div>
  );
}
