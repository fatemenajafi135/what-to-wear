import { useRef, useState } from "react";

import { apiFetch, ApiError } from "@/lib/api-client";
import { useSignedPhotoUrl } from "@/lib/use-signed-photo-url";
import type { WardrobeItem } from "@/lib/types";

export function ClosetItemCard({ item }: { item: WardrobeItem }) {
  // Local override so a replace/remove reflects immediately without the
  // parent closet list needing to be refetched (Feature 008 US4).
  const [photoPath, setPhotoPath] = useState(item.photo_path ?? null);
  const [busy, setBusy] = useState(false);
  const [photoError, setPhotoError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const photoUrl = useSignedPhotoUrl(photoPath);

  async function handlePhotoSelected(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;

    setBusy(true);
    setPhotoError(null);
    const formData = new FormData();
    formData.append("photo", file);
    try {
      const updated = await apiFetch<WardrobeItem>(`/wardrobe/items/${item.id}/photo`, {
        method: "POST",
        body: formData,
      });
      setPhotoPath(updated.photo_path ?? null);
    } catch (err) {
      setPhotoError(err instanceof ApiError ? `Couldn't update the photo (${err.status}).` : "Couldn't update the photo.");
    } finally {
      setBusy(false);
    }
  }

  async function handleRemovePhoto() {
    setBusy(true);
    setPhotoError(null);
    try {
      await apiFetch<WardrobeItem>(`/wardrobe/items/${item.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ photo_path: null }),
      });
      setPhotoPath(null);
    } catch (err) {
      setPhotoError(err instanceof ApiError ? `Couldn't remove the photo (${err.status}).` : "Couldn't remove the photo.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card">
      {photoUrl && (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={photoUrl} alt={item.category.replace("_", " ")} className="closet-item-photo" />
      )}
      <div className="closet-item-swatches">
        {(item.colors ?? []).map((hex) => (
          <span key={hex} className="closet-item-swatch" style={{ backgroundColor: hex }} title={hex} />
        ))}
      </div>
      <div className="card-title">{item.category.replace("_", " ")}</div>
      <div className="closet-item-attrs">
        <div>
          <span>Formality</span>
          <span>{item.formality.replace("_", " ")}</span>
        </div>
        <div>
          <span>Warmth</span>
          <span>{item.warmth}/5</span>
        </div>
        <div>
          <span>Season</span>
          <span>{(item.season ?? []).join(", ")}</span>
        </div>
      </div>
      <div className="tag-toggle-group">
        {item.fabric && <span className="tag tag-neutral">{item.fabric}</span>}
        {item.pattern && <span className="tag tag-neutral">{item.pattern}</span>}
        {item.fit && <span className="tag tag-neutral">{item.fit}</span>}
      </div>
      <div className="closet-item-photo-controls">
        <input ref={fileInputRef} type="file" accept="image/*" onChange={handlePhotoSelected} hidden />
        <button
          type="button"
          className="btn btn-ghost"
          style={{ fontSize: 11 }}
          disabled={busy}
          onClick={() => fileInputRef.current?.click()}
        >
          {photoPath ? "Replace photo" : "Add photo"}
        </button>
        {photoPath && (
          <button type="button" className="btn btn-ghost" style={{ fontSize: 11 }} disabled={busy} onClick={handleRemovePhoto}>
            Remove photo
          </button>
        )}
      </div>
      {photoError && <p className="page-error" style={{ fontSize: 11, margin: 0 }}>{photoError}</p>}
    </div>
  );
}
