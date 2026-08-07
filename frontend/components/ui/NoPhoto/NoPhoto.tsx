import { ImageOff } from "lucide-react";
import styles from "./NoPhoto.module.css";

export interface NoPhotoProps {
  className?: string;
}

/**
 * research.md §11 (specs/006-photo-upload-vision): the treatment for an
 * item with no photo at all (seeded before this feature shipped) — a
 * plain `--color-surface-sunken` fill with a centered icon, NOT the
 * removed diagonal-stripe placeholder repurposed as a stand-in
 * (design-system.md § Image treatment is explicit that the striped
 * pattern should be deleted outright). `aria-hidden` — conveys no
 * information a screen reader needs beyond the item's own name, already
 * announced by the surrounding link/heading. Shared between the Closet
 * grid tile and Item detail's hero — the two concrete call sites that
 * justify a shared component per the constitution's Quality Bar.
 */
export function NoPhoto({ className }: NoPhotoProps) {
  return (
    <div className={[styles.noPhoto, className].filter(Boolean).join(" ")} aria-hidden="true">
      <ImageOff size={28} strokeWidth={2} />
    </div>
  );
}
