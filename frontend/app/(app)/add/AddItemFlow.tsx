"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button/Button";
import { Banner } from "@/components/ui/Banner/Banner";
import { Dropzone } from "./Dropzone";
import { ReviewCard, type ReviewCardFields } from "./ReviewCard";
import { OrientationAwarePhoto, type PhotoRegion } from "./OrientationAwarePhoto";
import { buildFromUploadBody } from "./fromUploadBody";
import { apiClient } from "@/lib/api/client";
import { addItemCopy } from "@/lib/add-item-copy";
import type { components } from "@/lib/api/schema";
import styles from "./AddItemFlow.module.css";

type ExtractedAttributes = components["schemas"]["ExtractedAttributes"];

const FULL_REGION: PhotoRegion = { x: 0, y: 0, width: 1, height: 1 };

/** One reviewable garment from this photo — feature 018: a single upload
 * can now yield several (spec.md FR-023/FR-025), reviewed in place exactly
 * as a small bulk batch would be. */
interface Draft {
  photoPath: string;
  region: PhotoRegion;
  backgroundColor: string | null;
  extracted: ExtractedAttributes | null;
  isolatedPhotoUrl: string | null;
  isolatedPhotoPath: string | null;
}

type FlowState =
  | { step: "dropzone" }
  | { step: "scanning"; photoUrl: string }
  | {
      step: "review";
      photoUrl: string;
      drafts: Draft[];
      currentIndex: number;
      truncated: boolean;
    }
  | { step: "empty"; photoUrl: string; photoPath: string; backgroundColor: string | null }
  | { step: "error" }
  | { step: "saved" };

export interface AddItemFlowPosition {
  current: number;
  total: number;
}

export interface AddItemFlowProps {
  onClose: () => void;
  /** Feature 018: mirrors BulkQueue's `onPositionChange` (issue #32's
   * sticky-header pattern) — fires only once this photo has yielded more
   * than one detection (FR-025's "reviewed the same way a bulk upload's
   * multiple cards are"); stays `null` for the ordinary single-garment
   * case so that flow's experience is untouched (spec.md FR-004). */
  onPositionChange?: (position: AddItemFlowPosition | null) => void;
}

/**
 * design/design-system.md § Add item: dropzone → scan → review card →
 * saved (spec.md User Story 1). Extraction failure ("no garment found") is
 * a distinct, non-error empty state (FR-003); a genuine upload/scan
 * service failure is its own error state (FR-004) — never the same UI.
 * "Enter manually" from the empty state advances to the SAME review card,
 * blank, rather than a second form (FR-016, research.md §8).
 *
 * Feature 018: one photo can now yield several detections (drafts), each
 * reviewed and saved one at a time in place — the single-photo entry
 * point stays the entry point (FR-025); it does not fork into a second
 * "bulk-like" screen. The pre-018 single-detection path (exactly one
 * draft) behaves identically to before, including showing no position
 * indicator at all — see `onPositionChange` above.
 */
export function AddItemFlow({ onClose, onPositionChange }: AddItemFlowProps) {
  const [state, setState] = useState<FlowState>({ step: "dropzone" });
  const [saveError, setSaveError] = useState(false);

  useEffect(() => {
    if (state.step === "review" && state.drafts.length > 1) {
      onPositionChange?.({ current: state.currentIndex + 1, total: state.drafts.length });
    } else {
      onPositionChange?.(null);
    }
  }, [state, onPositionChange]);

  const handleFileSelected = async (file: File) => {
    const photoUrl = URL.createObjectURL(file);
    setState({ step: "scanning", photoUrl });
    try {
      const formData = new FormData();
      formData.append("photo", file);
      // Multipart request bodies don't type usefully through
      // openapi-typescript (research.md §10) — raw FormData is passed
      // directly; openapi-fetch skips its JSON-stringify step for it. The
      // *response* type is still fully generated.
      const { data, error } = await apiClient.POST("/api/v1/closet/items/extract", {
        // @ts-expect-error — multipart request body isn't usefully typed (research.md §10)
        body: formData,
      });
      const drafts = data?.drafts ?? [];
      if (error || drafts.length === 0) {
        setState({ step: "error" });
        return;
      }
      // A single draft with extraction_ok=false is today's exact
      // "nothing found" fallback (spec.md FR-003) — same empty-state
      // treatment as before feature 018, keyed the same way. Every other
      // shape (one successful draft, or several) goes to the review queue.
      if (drafts.length === 1 && !drafts[0]?.extraction_ok) {
        const only = drafts[0]!;
        setState({
          step: "empty",
          photoUrl,
          photoPath: only.photo_path,
          backgroundColor: only.extracted.background_color ?? null,
        });
        return;
      }
      setState({
        step: "review",
        photoUrl,
        truncated: data?.truncated ?? false,
        currentIndex: 0,
        drafts: drafts.map((draft) => ({
          photoPath: draft.photo_path,
          region: draft.region,
          backgroundColor: draft.extracted.background_color ?? null,
          extracted: draft.extraction_ok ? draft.extracted : null,
          isolatedPhotoUrl: draft.isolated_photo_url ?? null,
          isolatedPhotoPath: draft.isolated_photo_path ?? null,
        })),
      });
    } catch {
      setState({ step: "error" });
    }
  };

  const handleEnterManually = () => {
    if (state.step !== "empty") return;
    setState({
      step: "review",
      photoUrl: state.photoUrl,
      truncated: false,
      currentIndex: 0,
      drafts: [
        {
          photoPath: state.photoPath,
          region: FULL_REGION,
          backgroundColor: state.backgroundColor,
          extracted: null,
          isolatedPhotoUrl: null,
          isolatedPhotoPath: null,
        },
      ],
    });
  };

  const handleSave = async (fields: ReviewCardFields) => {
    if (state.step !== "review") return;
    const draft = state.drafts[state.currentIndex];
    if (!draft) return;
    setSaveError(false);
    const { error } = await apiClient.POST("/api/v1/closet/items/from-upload", {
      body: buildFromUploadBody(draft.photoPath, draft.isolatedPhotoPath, draft.backgroundColor, fields),
    });
    if (error) {
      // Not thrown — ReviewCard's own submit handler awaits onSave inside
      // try/finally with no catch, so throwing here would surface as an
      // unhandled promise rejection. `saveError` is a prop, matching
      // BulkQueue's identical fix.
      setSaveError(true);
      return;
    }
    const isLast = state.currentIndex === state.drafts.length - 1;
    if (isLast) {
      setState({ step: "saved" });
      onClose();
    } else {
      setState({ ...state, currentIndex: state.currentIndex + 1 });
    }
  };

  if (state.step === "dropzone") {
    return <Dropzone onFileSelected={handleFileSelected} />;
  }

  if (state.step === "scanning") {
    return (
      <div className={styles.stateBlock} aria-live="polite">
        <div className={styles.scanningPhotoWrap}>
          <OrientationAwarePhoto src={state.photoUrl} />
          <div className={`skeleton ${styles.scanningOverlay}`} />
        </div>
        <p className={`textBody ${styles.stateBody}`}>Scanning…</p>
      </div>
    );
  }

  if (state.step === "empty") {
    return (
      <div className={styles.stateBlock}>
        <OrientationAwarePhoto src={state.photoUrl} />
        <p className={`textBody ${styles.stateBody}`}>{addItemCopy.empty.body}</p>
        <Button width="intrinsic" onClick={() => setState({ step: "dropzone" })}>
          {addItemCopy.empty.retakeCta}
        </Button>
        <button type="button" className={styles.manualLink} onClick={handleEnterManually}>
          {addItemCopy.empty.enterManuallyCta}
        </button>
      </div>
    );
  }

  if (state.step === "error") {
    return (
      <div className={styles.stateBlock}>
        <p className={`textBody ${styles.stateBody}`}>{addItemCopy.error.body}</p>
        <Button width="intrinsic" onClick={() => setState({ step: "dropzone" })}>
          {addItemCopy.error.cta}
        </Button>
      </div>
    );
  }

  if (state.step === "review") {
    const draft = state.drafts[state.currentIndex];
    const e = draft?.extracted;
    const isLast = state.currentIndex === state.drafts.length - 1;
    return (
      <>
        {state.truncated && state.currentIndex === state.drafts.length - 1 && (
          <Banner variant="info">{addItemCopy.truncated.body}</Banner>
        )}
        <ReviewCard
          key={state.currentIndex}
          photoUrl={state.photoUrl}
          region={draft?.region}
          isolatedPhotoUrl={draft?.isolatedPhotoUrl}
          initial={{
            category: e?.category ?? "",
            fabric: e?.fabric ?? "",
            // Hex, exactly as detected — the card displays the derived names
            // via initialColorNames but sends the hex back untouched.
            colors: e?.colors ?? [],
            formality: e?.formality ?? "",
            warmth: e?.warmth == null ? "" : String(e.warmth),
            season: e?.season ?? [],
            pattern: e?.pattern ?? "",
            fit: e?.fit ?? "",
          }}
          saveLabel={isLast ? "Save to Closet" : "Save & next"}
          saveError={saveError}
          onSave={handleSave}
        />
      </>
    );
  }

  return null;
}
