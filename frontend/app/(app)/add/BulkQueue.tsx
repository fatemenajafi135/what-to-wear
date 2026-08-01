"use client";

import { useEffect, useRef, useState } from "react";
import { ReviewCard, type ReviewCardFields } from "./ReviewCard";
import { apiClient } from "@/lib/api/client";
import { addItemCopy } from "@/lib/add-item-copy";
import type { components } from "@/lib/api/schema";
import styles from "./BulkQueue.module.css";

type ExtractedAttributes = components["schemas"]["ExtractedAttributes"];

interface QueueEntry {
  file: File;
  photoUrl: string;
  status: "scanning" | "ready" | "saving" | "saved" | "save-error";
  photoPath?: string;
  extracted?: ExtractedAttributes | null;
  colorNames?: string[];
}

export interface BulkQueueProps {
  files: File[];
  onClose: () => void;
}

/**
 * design/design-system.md § Add item: bulk upload produces a queue of
 * review cards, one item per photo — "Save & next" advances, "Save to
 * Closet" finishes (spec.md User Story 2). Every photo is scanned upfront
 * (a real queue of ready cards, not scan-on-arrival) so the position
 * indicator and progress bar reflect the whole batch from the start.
 *
 * A card whose scan call genuinely fails (not "no garment found", which
 * is folded into the same blank-review-card treatment FR-016 already
 * establishes for the single-item flow) still becomes a `ready` entry
 * with everything blank — the design names no distinct per-card
 * extraction-failure UI for the bulk queue, and a blank, user-completable
 * card is strictly better than blocking the whole batch on one photo.
 *
 * Per-card SAVE failure is isolated (FR-008, research.md §6): the failed
 * card shows Button's Error treatment in place; already-saved cards are
 * unaffected; the queue does not advance past it until retried.
 */
export function BulkQueue({ files, onClose }: BulkQueueProps) {
  const [entries, setEntries] = useState<QueueEntry[]>(() =>
    files.map((file) => ({ file, photoUrl: URL.createObjectURL(file), status: "scanning" }))
  );
  const [currentIndex, setCurrentIndex] = useState(0);
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return;
    started.current = true;

    (async () => {
      for (let i = 0; i < files.length; i++) {
        const file = files[i];
        if (!file) continue;
        const formData = new FormData();
        formData.append("photo", file);
        try {
          const { data } = await apiClient.POST("/api/v1/closet/items/extract", {
            // @ts-expect-error — multipart request body isn't usefully typed (research.md §10)
            body: formData,
          });
          setEntries((prev) =>
            prev.map((entry, idx) =>
              idx === i
                ? {
                    ...entry,
                    status: "ready",
                    photoPath: data?.photo_path,
                    extracted: data?.extraction_ok ? data.extracted : null,
                    colorNames: data?.extraction_ok ? data.color_names : [],
                  }
                : entry
            )
          );
        } catch {
          setEntries((prev) =>
            prev.map((entry, idx) => (idx === i ? { ...entry, status: "ready", extracted: null, colorNames: [] } : entry))
          );
        }
      }
    })();
  }, [files]);

  const total = entries.length;
  const current = entries[currentIndex];
  const isLast = currentIndex === total - 1;
  const savedCount = entries.filter((e) => e.status === "saved").length;

  const handleSave = async (fields: ReviewCardFields) => {
    if (!current?.photoPath) return;
    setEntries((prev) => prev.map((e, idx) => (idx === currentIndex ? { ...e, status: "saving" } : e)));
    const { error } = await apiClient.POST("/api/v1/closet/items/from-upload", {
      body: {
        photo_path: current.photoPath,
        category: fields.category,
        colors: [fields.color],
        name: fields.name || null,
        fabric: fields.fabric || null,
        notes: fields.notes || null,
      },
    });
    if (error) {
      // Not thrown — `saveError` is a prop ReviewCard already reads
      // (research.md §6), not an exception it has to catch. Throwing here
      // would become an unhandled promise rejection: ReviewCard's own
      // submit handler awaits onSave inside try/finally with no catch.
      setEntries((prev) => prev.map((e, idx) => (idx === currentIndex ? { ...e, status: "save-error" } : e)));
      return;
    }
    setEntries((prev) => prev.map((e, idx) => (idx === currentIndex ? { ...e, status: "saved" } : e)));
    if (isLast) {
      onClose();
    } else {
      setCurrentIndex((idx) => idx + 1);
    }
  };

  if (!current || current.status === "scanning") {
    return <div aria-live="polite">Scanning…</div>;
  }

  return (
    <div className={styles.queue}>
      <h2 className={`textSectionTitle ${styles.position}`} aria-live="polite">
        {addItemCopy.review.position(currentIndex + 1, total)}
      </h2>
      <div className={styles.progressTrack} aria-hidden="true">
        <div className={styles.progressFill} style={{ width: `${((savedCount + 1) / total) * 100}%` }} />
      </div>
      <ReviewCard
        key={currentIndex}
        photoUrl={current.photoUrl}
        initial={{
          category: current.extracted?.category ?? "",
          fabric: current.extracted?.fabric ?? "",
          color: current.colorNames?.[0] ?? "",
        }}
        saveLabel={isLast ? "Save to Closet" : "Save & next"}
        saveError={current.status === "save-error"}
        onSave={handleSave}
      />
    </div>
  );
}
