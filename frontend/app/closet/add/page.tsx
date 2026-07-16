"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch, ApiError, redirectToSignIn, restoreDraft } from "@/lib/api-client";
import type { CreateWardrobeItemFromUploadRequest, ExtractedAttributes, PhotoExtractionResponse } from "@/lib/types";
import { ExtractedItemForm, draftFromExtracted, type ExtractedItemFormValue } from "@/components/ExtractedItemForm";

const DRAFT_KEY = "wtw:add-item-draft";

interface Draft {
  photoPath: string;
  extractionOk: boolean;
  formValue: ExtractedItemFormValue;
}

// A prior attempt may have been interrupted by an expired session mid-save
// (spec Edge Cases) -- resume exactly where the user left off instead of
// making them re-upload the photo and re-enter everything. Read once, as
// lazy initial state (not an effect -- there's nothing to subscribe to,
// this is a one-time read of an external store on first render); guarded
// for SSR, where sessionStorage doesn't exist.
function readResumedDraft(): Draft | null {
  if (typeof window === "undefined") return null;
  return restoreDraft<Draft>(DRAFT_KEY);
}

export default function AddItemPage() {
  const router = useRouter();
  const [resumedDraft] = useState<Draft | null>(readResumedDraft);
  const [step, setStep] = useState<"capture" | "review">(resumedDraft ? "review" : "capture");
  const [extracting, setExtracting] = useState(false);
  const [extractError, setExtractError] = useState<string | null>(null);
  const [photoPath, setPhotoPath] = useState<string | null>(resumedDraft?.photoPath ?? null);
  const [extractionOk, setExtractionOk] = useState(resumedDraft?.extractionOk ?? true);
  const [formInitial, setFormInitial] = useState<ExtractedItemFormValue | null>(resumedDraft?.formValue ?? null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  async function handleFileSelected(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;

    setExtracting(true);
    setExtractError(null);

    const formData = new FormData();
    formData.append("photo", file);

    try {
      const result = await apiFetch<PhotoExtractionResponse>("/wardrobe/items/extract", {
        method: "POST",
        body: formData,
      });
      setPhotoPath(result.photo_path);
      setExtractionOk(result.extraction_ok);
      setFormInitial(draftFromExtracted(result.extracted as ExtractedAttributes));
      setStep("review");
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        redirectToSignIn();
        return;
      }
      // A genuine upload-call failure (Storage unreachable, network drop --
      // distinct from "couldn't read the photo", which is extraction_ok:
      // false on a normal 200, handled above). No photo was actually
      // stored, so there's nothing to save yet -- stay on capture and let
      // the user retry, rather than continuing to a review step with no
      // real photo behind it.
      setExtractError("Something went wrong uploading that photo. Please try again.");
    } finally {
      setExtracting(false);
    }
  }

  async function handleSave(payload: CreateWardrobeItemFromUploadRequest) {
    setSaving(true);
    setSaveError(null);
    try {
      await apiFetch("/wardrobe/items/upload", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      router.push("/closet");
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        const draft: Draft = {
          photoPath: payload.photo_path,
          extractionOk,
          formValue: {
            category: payload.category,
            colors: payload.colors,
            formality: payload.formality,
            warmth: payload.warmth,
            season: payload.season,
            fabric: payload.fabric,
            pattern: payload.pattern,
            fit: payload.fit,
          },
        };
        redirectToSignIn(DRAFT_KEY, draft);
        return;
      }
      setSaveError("Couldn't save this item. Please try again.");
      setSaving(false);
    }
  }

  return (
    <div className="add-item-page">
      <h1>Add an item</h1>

      {step === "capture" && (
        <div className="card" style={{ maxWidth: 460 }}>
          <p className="text-muted">
            Take a photo, or choose one from your gallery, of a single garment or accessory.
          </p>
          <label htmlFor="photo-input" className="btn btn-primary btn-block">
            {extracting ? "Analyzing photo…" : "Choose or take a photo"}
          </label>
          <input
            id="photo-input"
            type="file"
            accept="image/*"
            capture="environment"
            onChange={handleFileSelected}
            disabled={extracting}
            style={{ position: "absolute", width: 1, height: 1, overflow: "hidden", opacity: 0 }}
          />
          {extractError && <p className="page-error">{extractError}</p>}
        </div>
      )}

      {step === "review" && photoPath !== null && formInitial !== null && (
        <ExtractedItemForm
          photoPath={photoPath}
          initial={formInitial}
          extractionOk={extractionOk}
          onSave={handleSave}
          saving={saving}
        />
      )}
      {saveError && <p className="page-error">{saveError}</p>}
    </div>
  );
}
