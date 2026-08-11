"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/Button/Button";
import { ReviewCard, type ReviewCardFields } from "./ReviewCard";
import { OrientationAwarePhoto } from "./OrientationAwarePhoto";
import { buildFromUploadBody } from "./fromUploadBody";
import { apiClient } from "@/lib/api/client";
import { addItemCopy } from "@/lib/add-item-copy";
import type { components } from "@/lib/api/schema";
import styles from "./BulkQueue.module.css";

type ExtractedAttributes = components["schemas"]["ExtractedAttributes"];

interface QueueEntry {
  file: File;
  photoUrl: string;
  status: "scanning" | "ready" | "upload-error" | "saving" | "saved" | "save-error";
  photoPath?: string;
  backgroundColor?: string | null;
  extracted?: ExtractedAttributes | null;
}

export interface BulkQueuePosition {
  current: number;
  total: number;
}

export interface BulkQueueProps {
  files: File[];
  onClose: () => void;
  /** issue #32: the "Reviewing item X of Y" indicator moved up to the page's
   * sticky header, since it needs to stay fixed alongside it — this reports
   * it upward instead of rendering it inline. Fires with `null` whenever
   * the indicator shouldn't show (the same "scanning" gate the inline
   * version used). */
  onPositionChange?: (position: BulkQueuePosition | null) => void;
}

/**
 * design/design-system.md § Add item: bulk upload produces a queue of
 * review cards, one item per photo — "Save & next" advances, "Save to
 * Closet" finishes (spec.md User Story 2). Every photo is scanned upfront
 * (a real queue of ready cards, not scan-on-arrival) so the position
 * indicator and progress bar reflect the whole batch from the start.
 *
 * Two different failures hide behind one call, and conflating them is what
 * broke this screen in practice:
 *
 * - The upload SUCCEEDED but extraction found nothing usable. The photo is
 *   in Storage and `photo_path` came back, so the card is perfectly
 *   saveable — it just starts blank. That is the `ready` treatment, and
 *   folding it in with "no garment found" is right (FR-016 does the same
 *   for the single-item flow).
 * - The upload itself FAILED, so there is no `photo_path` at all. Such a
 *   card can never be saved, because `photo_path` is what
 *   `/closet/items/from-upload` is keyed on.
 *
 * The original version marked BOTH `ready`, then had `handleSave` bail with
 * a bare `if (!current?.photoPath) return;`. The second kind rendered as a
 * completely ordinary card whose Save button silently did nothing, forever
 * — no error, no request, no log. A real batch of nine photos produced
 * fifteen extract calls and zero saves, with nothing on screen to explain
 * it. So the two now have distinct states, and a failed upload gets the
 * design's own error copy plus a per-photo retry.
 *
 * Per-card SAVE failure is isolated (FR-008, research.md §6): the failed
 * card shows Button's Error treatment in place; already-saved cards are
 * unaffected; the queue does not advance past it until retried.
 */
export function BulkQueue({ files, onClose, onPositionChange }: BulkQueueProps) {
  const [entries, setEntries] = useState<QueueEntry[]>(() =>
    files.map((file) => ({ file, photoUrl: URL.createObjectURL(file), status: "scanning" }))
  );
  const [currentIndex, setCurrentIndex] = useState(0);
  const started = useRef(false);

  /** Scans one photo. Reusable so a failed upload can be retried in place
   * without re-selecting the whole batch. */
  const scanEntry = useCallback(async (index: number, file: File) => {
    setEntries((prev) => prev.map((entry, idx) => (idx === index ? { ...entry, status: "scanning" } : entry)));

    const formData = new FormData();
    formData.append("photo", file);

    let photoPath: string | undefined;
    let backgroundColor: string | null = null;
    let extracted: ExtractedAttributes | null = null;
    try {
      const { data } = await apiClient.POST("/api/v1/closet/items/extract", {
        // @ts-expect-error — multipart request body isn't usefully typed (research.md §10)
        body: formData,
      });
      photoPath = data?.photo_path;
      backgroundColor = data?.extracted?.background_color ?? null;
      if (data?.extraction_ok) {
        extracted = data.extracted;
      }
    } catch {
      // Leaves photoPath undefined — handled identically to a non-2xx
      // response below, since both mean "nothing landed in Storage".
    }

    setEntries((prev) =>
      prev.map((entry, idx) => {
        if (idx !== index) return entry;
        // No photo_path means the upload failed, not that the scan came
        // back empty — this card could never be saved, so it must say so
        // rather than pose as an ordinary blank one.
        return photoPath
          ? { ...entry, status: "ready", photoPath, backgroundColor, extracted }
          : { ...entry, status: "upload-error", photoPath: undefined, extracted: null };
      })
    );
  }, []);

  useEffect(() => {
    if (started.current) return;
    started.current = true;

    (async () => {
      for (let i = 0; i < files.length; i++) {
        const file = files[i];
        if (!file) continue;
        await scanEntry(i, file);
      }
    })();
  }, [files, scanEntry]);

  const total = entries.length;
  const current = entries[currentIndex];
  const isLast = currentIndex === total - 1;
  const savedCount = entries.filter((e) => e.status === "saved").length;

  useEffect(() => {
    onPositionChange?.(current && current.status !== "scanning" ? { current: currentIndex + 1, total } : null);
  }, [current, currentIndex, total, onPositionChange]);

  const advance = () => {
    if (isLast) {
      onClose();
    } else {
      setCurrentIndex((idx) => idx + 1);
    }
  };

  const handleSave = async (fields: ReviewCardFields) => {
    if (!current?.photoPath) {
      // Defensive: `upload-error` is rendered before a ReviewCard ever
      // mounts for such an entry, so this is unreachable. It marks the
      // card rather than returning silently, because returning silently
      // is exactly the bug this file was fixed for.
      setEntries((prev) => prev.map((e, idx) => (idx === currentIndex ? { ...e, status: "upload-error" } : e)));
      return;
    }
    setEntries((prev) => prev.map((e, idx) => (idx === currentIndex ? { ...e, status: "saving" } : e)));
    const { error } = await apiClient.POST("/api/v1/closet/items/from-upload", {
      body: buildFromUploadBody(current.photoPath, current.backgroundColor, fields),
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
    advance();
  };

  if (!current) {
    return <div aria-live="polite">Scanning…</div>;
  }

  if (current.status === "scanning") {
    return (
      <div className={styles.scanningBlock} aria-live="polite">
        <div className={styles.scanningPhotoWrap}>
          <OrientationAwarePhoto src={current.photoUrl} />
          <div className={`skeleton ${styles.scanningOverlay}`} />
        </div>
        <p className={`textBody ${styles.scanningCaption}`}>Scanning…</p>
      </div>
    );
  }

  if (current.status === "upload-error") {
    return (
      <div className={styles.queue}>
        <div className={styles.uploadError} role="alert">
          <OrientationAwarePhoto src={current.photoUrl} />
          <p className={`textBody ${styles.errorBody}`}>{addItemCopy.error.body}</p>
          <Button width="intrinsic" onClick={() => void scanEntry(currentIndex, current.file)}>
            {addItemCopy.error.cta}
          </Button>
          {/* Without this, one permanently failing photo strands the rest of
              the batch behind it — the queue only ever moves forward on a
              successful save. */}
          <button type="button" className={styles.skipLink} onClick={advance}>
            {addItemCopy.review.skipCta(isLast)}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.queue}>
      <div className={styles.progressTrack} aria-hidden="true">
        <div className={styles.progressFill} style={{ width: `${((savedCount + 1) / total) * 100}%` }} />
      </div>
      <ReviewCard
        key={currentIndex}
        photoUrl={current.photoUrl}
        initial={{
          category: current.extracted?.category ?? "",
          fabric: current.extracted?.fabric ?? "",
          colors: current.extracted?.colors ?? [],
          formality: current.extracted?.formality ?? "",
          warmth: current.extracted?.warmth == null ? "" : String(current.extracted.warmth),
          season: current.extracted?.season ?? [],
          pattern: current.extracted?.pattern ?? "",
          fit: current.extracted?.fit ?? "",
        }}
        saveLabel={isLast ? "Save to Closet" : "Save & next"}
        saveError={current.status === "save-error"}
        onSave={handleSave}
      />
      {/* issue #62: generalizes the upload-error skip above to the normal
          review state — same copy, same style, same one-tap "just move on"
          behaviour (docs/design-decisions.md §64). Sits below the form as a
          sibling rather than inside ReviewCard's <form>, so a tap can never
          be mistaken for (or trigger) a submit. Disabled mid-save so a skip
          can't race an in-flight save request for the same card. */}
      <button
        type="button"
        className={styles.skipLink}
        onClick={advance}
        disabled={current.status === "saving"}
      >
        {addItemCopy.review.skipCta(isLast)}
      </button>
    </div>
  );
}
