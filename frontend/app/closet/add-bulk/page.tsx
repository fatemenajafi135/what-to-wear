"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch, ApiError, redirectToSignIn } from "@/lib/api-client";
import type { CreateWardrobeItemFromUploadRequest, ExtractedAttributes, PhotoExtractionResponse } from "@/lib/types";
import { ExtractedItemForm, draftFromExtracted, type ExtractedItemFormValue } from "@/components/ExtractedItemForm";

const MAX_BATCH_SIZE = 30;

type BatchItemStatus = "extracting" | "ready" | "saving" | "saved" | "save-failed";

interface BatchItem {
  file: File;
  status: BatchItemStatus;
  photoPath: string | null;
  extractionOk: boolean;
  formValue: ExtractedItemFormValue | null;
}

export default function AddBulkItemsPage() {
  const router = useRouter();
  const [step, setStep] = useState<"select" | "extracting" | "review" | "done">("select");
  const [items, setItems] = useState<BatchItem[]>([]);
  const [reviewIndex, setReviewIndex] = useState(0);
  const [capError, setCapError] = useState<string | null>(null);
  const [savedCount, setSavedCount] = useState(0);

  async function handleFilesSelected(e: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files ?? []);
    if (files.length === 0) return;

    if (files.length > MAX_BATCH_SIZE) {
      setCapError(`You can add up to ${MAX_BATCH_SIZE} photos at once -- you selected ${files.length}.`);
      return;
    }
    setCapError(null);

    setStep("extracting");
    const initial: BatchItem[] = files.map((file) => ({
      file,
      status: "extracting",
      photoPath: null,
      extractionOk: true,
      formValue: null,
    }));
    setItems(initial);

    // Sequential, not concurrent -- see plan.md's Research section: keeps
    // load on the extraction gateway bounded and gives per-item progress
    // for free, which a batch this size needs anyway.
    for (let i = 0; i < initial.length; i++) {
      const formData = new FormData();
      formData.append("photo", initial[i].file);
      try {
        const result = await apiFetch<PhotoExtractionResponse>("/wardrobe/items/extract", {
          method: "POST",
          body: formData,
        });
        setItems((prev) =>
          prev.map((it, idx) =>
            idx === i
              ? {
                  ...it,
                  status: "ready",
                  photoPath: result.photo_path,
                  extractionOk: result.extraction_ok,
                  formValue: draftFromExtracted(result.extracted as ExtractedAttributes),
                }
              : it
          )
        );
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) {
          redirectToSignIn();
          return;
        }
        // Extraction failing for one photo falls back to the same
        // manual-entry path the single-item flow already uses -- it still
        // enters review, just with a blank form (FR-004).
        setItems((prev) =>
          prev.map((it, idx) =>
            idx === i
              ? {
                  ...it,
                  status: "ready",
                  photoPath: null,
                  extractionOk: false,
                  formValue: draftFromExtracted({}),
                }
              : it
          )
        );
      }
    }

    setStep("review");
    setReviewIndex(0);
  }

  async function handleSaveCurrent(payload: CreateWardrobeItemFromUploadRequest) {
    setItems((prev) => prev.map((it, idx) => (idx === reviewIndex ? { ...it, status: "saving" } : it)));
    try {
      await apiFetch("/wardrobe/items/upload", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      setItems((prev) => prev.map((it, idx) => (idx === reviewIndex ? { ...it, status: "saved" } : it)));
      setSavedCount((c) => c + 1);
      advance();
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        redirectToSignIn();
        return;
      }
      // A save failure on this item never touches items that already
      // saved -- the user can retry just this one (FR-005).
      setItems((prev) => prev.map((it, idx) => (idx === reviewIndex ? { ...it, status: "save-failed" } : it)));
    }
  }

  function advance() {
    setReviewIndex((i) => {
      const next = i + 1;
      if (next >= items.length) {
        setStep("done");
        return i;
      }
      return next;
    });
  }

  function skipCurrent() {
    advance();
  }

  const current = items[reviewIndex];

  return (
    <div className="add-item-page">
      <h1>Add multiple items</h1>

      {step === "select" && (
        <div className="card" style={{ maxWidth: 460 }}>
          <p className="text-muted">
            Select up to {MAX_BATCH_SIZE} photos at once -- one garment or accessory per photo.
          </p>
          <label htmlFor="bulk-photo-input" className="btn btn-primary btn-block">
            Choose photos
          </label>
          <input
            id="bulk-photo-input"
            type="file"
            accept="image/*"
            multiple
            onChange={handleFilesSelected}
            style={{ position: "absolute", width: 1, height: 1, overflow: "hidden", opacity: 0 }}
          />
          {capError && <p className="page-error">{capError}</p>}
        </div>
      )}

      {step === "extracting" && (
        <div className="card" style={{ maxWidth: 460 }}>
          <p className="text-muted">
            Analyzing photo {items.filter((it) => it.status !== "extracting").length + 1} of {items.length}…
          </p>
        </div>
      )}

      {step === "review" && current && (
        <>
          <p className="text-muted">
            Reviewing item {reviewIndex + 1} of {items.length}
            {savedCount > 0 ? ` -- ${savedCount} saved so far` : ""}
          </p>
          {current.status === "save-failed" && (
            <div className="page-error" style={{ marginBottom: "var(--space-3)" }}>
              Couldn&apos;t save this item. Press &quot;Save to closet&quot; below to retry, or{" "}
              <button type="button" className="btn btn-ghost" onClick={skipCurrent}>
                skip it
              </button>
              .
            </div>
          )}
          {current.photoPath !== null && current.formValue !== null && (
            <ExtractedItemForm
              key={reviewIndex}
              photoPath={current.photoPath}
              initial={current.formValue}
              extractionOk={current.extractionOk}
              onSave={handleSaveCurrent}
              saving={current.status === "saving"}
            />
          )}
          {current.photoPath === null && current.formValue !== null && (
            // Extraction (and thus the photo upload itself) failed outright
            // for this item -- no photo_path exists to save against, so
            // there's nothing to confirm. Matches FR-004: doesn't block the
            // rest of the batch.
            <div className="card">
              <p className="page-error">This photo couldn&apos;t be uploaded or read. Skipping it.</p>
              <button type="button" className="btn btn-secondary" onClick={skipCurrent}>
                Continue
              </button>
            </div>
          )}
        </>
      )}

      {step === "done" && (
        <div className="card" style={{ maxWidth: 460 }}>
          <p>
            Saved {savedCount} of {items.length} items.
          </p>
          <button type="button" className="btn btn-primary btn-block" onClick={() => router.push("/closet")}>
            Go to closet
          </button>
        </div>
      )}
    </div>
  );
}
