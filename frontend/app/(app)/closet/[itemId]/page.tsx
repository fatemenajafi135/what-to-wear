"use client";

import { use, useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { TopHeader } from "@/components/ui/TopHeader/TopHeader";
import { Button } from "@/components/ui/Button/Button";
import { ItemPhoto } from "@/components/ui/ItemPhoto/ItemPhoto";
import { apiClient } from "@/lib/api/client";
import { useOnlineStatus } from "@/lib/useOnlineStatus";
import { ClosetGrid } from "../ClosetGrid";
import { ItemOverflowSheet } from "./ItemOverflowSheet";
import { ItemEditForm } from "./ItemEditForm";
import { DeleteConfirmDialog } from "./DeleteConfirmDialog";
import type { components } from "@/lib/api/schema";
import twoPaneStyles from "../page.module.css";
import styles from "./page.module.css";

type ClosetItemView = components["schemas"]["ClosetItemView"];

/**
 * `/closet/:itemId` — design/design-system.md § Item detail: header with
 * back + overflow (dots) trigger, photo placeholder, and the details card.
 * Feature 005 fills in the overflow sheet 004 wired the trigger for
 * (Edit / Log as worn today / Favorite / Delete), the edit-mode form, and
 * the delete confirmation dialog (docs/design-decisions.md §22.2).
 *
 * At ≥1024px (design-system.md §5's two-pane master-detail), the closet
 * grid renders in a pane to the left of this content, mirroring
 * `/closet/page.tsx`'s own two-pane composition.
 */
export default function ItemDetailPage({ params }: { params: Promise<{ itemId: string }> }) {
  const { itemId } = use(params);
  const router = useRouter();
  const [item, setItem] = useState<ClosetItemView | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState(false);
  const [editing, setEditing] = useState(false);
  const [sheetOpen, setSheetOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const isOnline = useOnlineStatus();

  const load = useCallback(async () => {
    setLoading(true);
    setNotFound(false);
    setError(false);
    try {
      const { data, response } = await apiClient.GET("/api/v1/closet/items/{item_id}", {
        params: { path: { item_id: itemId } },
      });
      if (response.status === 404) {
        setNotFound(true);
        return;
      }
      if (!data) {
        setError(true);
        return;
      }
      setItem(data);
    } catch {
      // Dropped connection (fetch rejects outright, distinct from a non-2xx
      // response) — most commonly hit while offline, resolves to the same
      // suppressed-error state `showError` already handles.
      setError(true);
    } finally {
      setLoading(false);
    }
  }, [itemId]);

  useEffect(() => {
    load();
  }, [load]);

  const showError = error && isOnline; // offline suppresses the screen-level error (design-system §6)

  const handleToggleFavorite = async () => {
    await apiClient.POST("/api/v1/closet/items/{item_id}/favorite", {
      params: { path: { item_id: itemId } },
    });
    // Never reflected on Item detail (design-system §2.3) — no local state
    // update needed beyond the request itself.
  };

  const handleLogWorn = async () => {
    await apiClient.POST("/api/v1/closet/items/{item_id}/wear", {
      params: { path: { item_id: itemId } },
    });
  };

  const handleDeleteConfirmed = async () => {
    setDeleteDialogOpen(false);
    const { response } = await apiClient.DELETE("/api/v1/closet/items/{item_id}", {
      params: { path: { item_id: itemId } },
    });
    if (response.ok) {
      router.push("/closet");
    }
  };

  return (
    <div className={twoPaneStyles.twoPane}>
      <div className={twoPaneStyles.gridPane}>
        <ClosetGrid selectedItemId={itemId} />
      </div>

      <div>
        <TopHeader
          title="Item details"
          backHref="/closet"
          rightSlot={{ kind: "icon", icon: "dots", onClick: () => setSheetOpen(true) }}
        />

        {loading && (
          // design-system.md § Per-screen skeleton layouts: Item detail's
          // skeleton is the three-bar card only, no photo placeholder.
          <div className={styles.wrapper} aria-hidden="true">
            <div className={styles.card}>
              <div className={`${styles.bar} ${styles.bar60} skeleton`} />
              <div className={`${styles.bar} ${styles.bar40} skeleton`} />
              <div className={`${styles.bar} ${styles.bar80} skeleton`} />
            </div>
          </div>
        )}

        {!loading && notFound && (
          <div className={styles.stateBlock}>
            <p className={`textBody ${styles.stateBody}`}>
              This item couldn&apos;t be found — it may have been removed.
            </p>
            <Button href="/closet" width="intrinsic">
              Back to Closet
            </Button>
          </div>
        )}

        {!loading && showError && (
          <div className={styles.stateBlock}>
            <p className={`textBody ${styles.stateBody}`}>Couldn&apos;t load your closet.</p>
            <Button width="intrinsic" onClick={load}>
              Retry
            </Button>
          </div>
        )}

        {!loading && !notFound && !error && item && !editing && <ItemDetailCard item={item} />}

        {!loading && !notFound && !error && item && editing && (
          <ItemEditForm
            item={item}
            isOnline={isOnline}
            onSaved={(updated) => {
              setItem(updated);
              setEditing(false);
            }}
          />
        )}

        {item && (
          <>
            <ItemOverflowSheet
              open={sheetOpen}
              onClose={() => setSheetOpen(false)}
              isOnline={isOnline}
              onEdit={() => setEditing(true)}
              onLogWorn={handleLogWorn}
              onToggleFavorite={handleToggleFavorite}
              onDelete={() => setDeleteDialogOpen(true)}
            />
            <DeleteConfirmDialog
              open={deleteDialogOpen}
              itemName={item.name ?? "this item"}
              onConfirm={handleDeleteConfirmed}
              onCancel={() => setDeleteDialogOpen(false)}
            />
          </>
        )}
      </div>
    </div>
  );
}

function ItemDetailCard({ item }: { item: ClosetItemView }) {
  const fields: { label: string; value: string }[] = [
    { label: "Name", value: item.name ?? "—" },
    { label: "Category", value: item.category_group },
    { label: "Group", value: item.category },
    { label: "Fabric", value: item.fabric ?? "—" },
    { label: "Colour", value: item.color_names.length > 0 ? item.color_names.join(", ") : "—" },
    { label: "Notes", value: item.notes ?? "—" },
  ];

  return (
    <div className={styles.wrapper}>
      <ItemPhoto
        src={item.photo_url}
        backgroundColor={item.photo_background_color}
        className={styles.photo}
        radius={16}
      />
      <div className={styles.card}>
        {fields.map((field) => (
          <div key={field.label} className={styles.fieldRow}>
            <span className={`textLabel ${styles.fieldLabel}`}>{field.label}</span>
            <span className={styles.fieldValue}>{field.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
