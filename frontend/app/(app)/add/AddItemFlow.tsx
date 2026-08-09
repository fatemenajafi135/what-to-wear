"use client";

import { useState } from "react";
import { Button } from "@/components/ui/Button/Button";
import { Dropzone } from "./Dropzone";
import { ReviewCard, type ReviewCardFields } from "./ReviewCard";
import { OrientationAwarePhoto } from "./OrientationAwarePhoto";
import { buildFromUploadBody } from "./fromUploadBody";
import { apiClient } from "@/lib/api/client";
import { addItemCopy } from "@/lib/add-item-copy";
import type { components } from "@/lib/api/schema";
import styles from "./AddItemFlow.module.css";

type ExtractedAttributes = components["schemas"]["ExtractedAttributes"];

type FlowState =
  | { step: "dropzone" }
  | { step: "scanning"; photoUrl: string }
  | {
      step: "review";
      photoUrl: string;
      photoPath: string;
      backgroundColor: string | null;
      extracted: ExtractedAttributes | null;
    }
  | { step: "empty"; photoUrl: string; photoPath: string; backgroundColor: string | null }
  | { step: "error" }
  | { step: "saved" };

export interface AddItemFlowProps {
  onClose: () => void;
}

/**
 * design/design-system.md § Add item: dropzone → scan → review card →
 * saved (spec.md User Story 1). Extraction failure ("no garment found") is
 * a distinct, non-error empty state (FR-003); a genuine upload/scan
 * service failure is its own error state (FR-004) — never the same UI.
 * "Enter manually" from the empty state advances to the SAME review card,
 * blank, rather than a second form (FR-016, research.md §8).
 */
export function AddItemFlow({ onClose }: AddItemFlowProps) {
  const [state, setState] = useState<FlowState>({ step: "dropzone" });
  const [saveError, setSaveError] = useState(false);

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
      if (error || !data) {
        setState({ step: "error" });
        return;
      }
      if (data.extraction_ok) {
        setState({
          step: "review",
          photoUrl,
          photoPath: data.photo_path,
          backgroundColor: data.extracted.background_color ?? null,
          extracted: data.extracted,
        });
      } else {
        setState({
          step: "empty",
          photoUrl,
          photoPath: data.photo_path,
          backgroundColor: data.extracted.background_color ?? null,
        });
      }
    } catch {
      setState({ step: "error" });
    }
  };

  const handleEnterManually = () => {
    if (state.step !== "empty") return;
    setState({
      step: "review",
      photoUrl: state.photoUrl,
      photoPath: state.photoPath,
      backgroundColor: state.backgroundColor,
      extracted: null,
    });
  };

  const handleSave = async (fields: ReviewCardFields, photoPath: string, backgroundColor: string | null) => {
    setSaveError(false);
    const { error } = await apiClient.POST("/api/v1/closet/items/from-upload", {
      body: buildFromUploadBody(photoPath, backgroundColor, fields),
    });
    if (error) {
      // Not thrown — ReviewCard's own submit handler awaits onSave inside
      // try/finally with no catch, so throwing here would surface as an
      // unhandled promise rejection. `saveError` is a prop, matching
      // BulkQueue's identical fix.
      setSaveError(true);
      return;
    }
    setState({ step: "saved" });
    onClose();
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
    const e = state.extracted;
    return (
      <ReviewCard
        photoUrl={state.photoUrl}
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
        saveLabel="Save to Closet"
        saveError={saveError}
        onSave={(fields) => handleSave(fields, state.photoPath, state.backgroundColor)}
      />
    );
  }

  return null;
}
