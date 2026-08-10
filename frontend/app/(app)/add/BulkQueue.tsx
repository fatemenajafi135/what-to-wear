"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/Button/Button";
import { Banner } from "@/components/ui/Banner/Banner";
import { ReviewCard, type ReviewCardFields } from "./ReviewCard";
import { OrientationAwarePhoto, type PhotoRegion } from "./OrientationAwarePhoto";
import { buildFromUploadBody } from "./fromUploadBody";
import { apiClient } from "@/lib/api/client";
import { addItemCopy } from "@/lib/add-item-copy";
import type { components } from "@/lib/api/schema";
import styles from "./BulkQueue.module.css";

type ExtractedAttributes = components["schemas"]["ExtractedAttributes"];
type PhotoExtractionView = components["schemas"]["PhotoExtractionView"];

interface QueueEntry {
  /** Groups entries produced by the same uploaded photo — index into
   * `files`. One photo now yields 1..8 entries instead of exactly 1
   * (feature 018, spec.md FR-023): the queue is keyed to detections, not
   * files, but a retry still needs to know which file+region to re-scan
   * and which entries in the flattened list to replace. */
  sourceIndex: number;
  file: File;
  photoUrl: string;
  status: "scanning" | "ready" | "upload-error" | "saving" | "saved" | "save-error";
  photoPath?: string;
  region?: PhotoRegion;
  backgroundColor?: string | null;
  extracted?: ExtractedAttributes | null;
  isolatedPhotoUrl?: string | null;
  isolatedPhotoPath?: string | null;
  /** True on this photo's LAST entry only, when its source photo had more
   * garments than the detection cap kept (spec.md FR-002) — shown once
   * per photo, not once per card. */
  truncated?: boolean;
}

/** Replaces every entry sharing `sourceIndex` with `replacements`, in
 * place — entries from the same photo are always contiguous (inserted as
 * one block, never interleaved with another photo's), so this is a
 * straightforward splice rather than a full re-sort. Falls back to
 * appending when `sourceIndex` has no entries yet (shouldn't happen: every
 * `sourceIndex` starts with one placeholder — defensive only). */
function replaceBySourceIndex(prev: QueueEntry[], sourceIndex: number, replacements: QueueEntry[]): QueueEntry[] {
  const start = prev.findIndex((e) => e.sourceIndex === sourceIndex);
  if (start === -1) return [...prev, ...replacements];
  let end = prev.findIndex((e, i) => i > start && e.sourceIndex !== sourceIndex);
  if (end === -1) end = prev.length;
  return [...prev.slice(0, start), ...replacements, ...prev.slice(end)];
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
 * review cards — one per DETECTED GARMENT as of feature 018 (spec.md
 * FR-023), not one per photo as it originally was: a flat-lay of several
 * items now expands into several cards from a single upload. "Save & next"
 * advances, "Save to Closet" finishes (spec.md User Story 2).
 *
 * Every photo is scanned upfront, concurrently, and — new in feature 018 —
 * the whole batch's scan must finish before ANY card is shown, not just
 * the first photo's. This is what makes the "Reviewing item X of Y"
 * total accurate the instant it appears (spec.md FR-024): the total is a
 * detection count summed across every photo, which isn't knowable until
 * every photo has actually been scanned — showing the queue after only
 * the first photo resolves would display a total that silently grows as
 * the rest finish in the background. `initialScanComplete` is that gate;
 * once it flips, every card/retry/save interaction below behaves exactly
 * like a single flat list of reviewable drafts, no different from before
 * this feature (a per-card `"scanning"` status still exists for retrying
 * one upload-error photo in place, which is intentionally NOT gated by
 * `initialScanComplete` — only the very first batch scan is).
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
  // Created once per file, independent of `entries`' own churn (a photo's
  // placeholder entry gets replaced by however many drafts it yields) —
  // both the initial state below and any later retry need the SAME blob
  // URL for a given file, never a fresh one.
  const photoUrls = useRef<string[]>(files.map((file) => URL.createObjectURL(file)));

  const [entries, setEntries] = useState<QueueEntry[]>(() =>
    files.map((file, sourceIndex) => ({
      sourceIndex,
      file,
      photoUrl: photoUrls.current[sourceIndex] ?? URL.createObjectURL(file),
      status: "scanning" as const,
    }))
  );
  const [initialScanComplete, setInitialScanComplete] = useState(false);
  const [currentIndex, setCurrentIndex] = useState(0);
  const started = useRef(false);

  /** Scans one photo, replacing every entry currently attributed to it.
   * Reusable so a failed upload can be retried in place without
   * re-selecting the whole batch — a retry replaces just that photo's
   * entry/entries, never touching any other photo's. */
  const scanEntry = useCallback(async (sourceIndex: number, file: File, photoUrl: string) => {
    setEntries((prev) => replaceBySourceIndex(prev, sourceIndex, [{ sourceIndex, file, photoUrl, status: "scanning" }]));

    const formData = new FormData();
    formData.append("photo", file);

    let drafts: PhotoExtractionView[] = [];
    let truncated = false;
    try {
      const { data } = await apiClient.POST("/api/v1/closet/items/extract", {
        // @ts-expect-error — multipart request body isn't usefully typed (research.md §10)
        body: formData,
      });
      drafts = data?.drafts ?? [];
      truncated = data?.truncated ?? false;
    } catch {
      // Leaves drafts empty — handled identically to a non-2xx response
      // below, since both mean "nothing landed in Storage".
    }

    setEntries((prev) => {
      // No drafts means no photo_path came back either — the upload
      // itself failed, not that the scan came back empty. Such a card
      // could never be saved, so it must say so rather than pose as an
      // ordinary blank one.
      if (drafts.length === 0 || !drafts[0]?.photo_path) {
        return replaceBySourceIndex(prev, sourceIndex, [{ sourceIndex, file, photoUrl, status: "upload-error" }]);
      }
      const replacements: QueueEntry[] = drafts.map((draft, i) => ({
        sourceIndex,
        file,
        photoUrl,
        status: "ready",
        photoPath: draft.photo_path,
        region: draft.region,
        backgroundColor: draft.extracted.background_color ?? null,
        extracted: draft.extraction_ok ? draft.extracted : null,
        isolatedPhotoUrl: draft.isolated_photo_url ?? null,
        isolatedPhotoPath: draft.isolated_photo_path ?? null,
        truncated: truncated && i === drafts.length - 1,
      }));
      return replaceBySourceIndex(prev, sourceIndex, replacements);
    });
  }, []);

  useEffect(() => {
    if (started.current) return;
    started.current = true;

    void Promise.all(files.map((file, i) => scanEntry(i, file, photoUrls.current[i] ?? ""))).then(() =>
      setInitialScanComplete(true)
    );
  }, [files, scanEntry]);

  const total = entries.length;
  const current = entries[currentIndex];
  const isLast = currentIndex === total - 1;
  const savedCount = entries.filter((e) => e.status === "saved").length;

  useEffect(() => {
    onPositionChange?.(
      initialScanComplete && current && current.status !== "scanning" ? { current: currentIndex + 1, total } : null
    );
  }, [initialScanComplete, current, currentIndex, total, onPositionChange]);

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
      body: buildFromUploadBody(current.photoPath, current.isolatedPhotoPath, current.backgroundColor, fields),
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

  if (!initialScanComplete) {
    return (
      <div className={styles.scanningBlock} aria-live="polite">
        <div className={styles.scanningPhotoWrap}>
          <OrientationAwarePhoto src={entries[0]?.photoUrl ?? ""} />
          <div className={`skeleton ${styles.scanningOverlay}`} />
        </div>
        <p className={`textBody ${styles.scanningCaption}`}>Scanning…</p>
      </div>
    );
  }

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
          <Button width="intrinsic" onClick={() => void scanEntry(current.sourceIndex, current.file, current.photoUrl)}>
            {addItemCopy.error.cta}
          </Button>
          {/* Without this, one permanently failing photo strands the rest of
              the batch behind it — the queue only ever moves forward on a
              successful save. */}
          <button type="button" className={styles.skipLink} onClick={advance}>
            {isLast ? "Skip and finish" : "Skip this photo"}
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
      {current.truncated && <Banner variant="info">{addItemCopy.truncated.body}</Banner>}
      <ReviewCard
        key={currentIndex}
        photoUrl={current.photoUrl}
        region={current.region}
        isolatedPhotoUrl={current.isolatedPhotoUrl}
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
    </div>
  );
}
