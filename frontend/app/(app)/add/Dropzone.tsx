"use client";

import { useRef, useState } from "react";
import { Camera } from "lucide-react";
import { CameraPrimer } from "@/components/camera/CameraPrimer";
import { isCameraPrimed, setCameraPrimed } from "@/lib/camera/primed";
import { addItemCopy } from "@/lib/add-item-copy";
import { useOnlineStatus } from "@/lib/useOnlineStatus";
import styles from "./Dropzone.module.css";

export interface DropzoneProps {
  onFileSelected: (file: File) => void;
}

/**
 * design/design-system.md § Image treatment: full-width, 220px, 16px
 * radius upload dropzone. Offline disables it entirely (FR-014) — no
 * retry-promise copy, matching design-system §6's offline convention.
 *
 * Camera gating (research.md §7 addendum, SC-006): the FIRST tap ever
 * (`isCameraPrimed()` false) shows `CameraPrimer` first. Accepting sets
 * primed and opens the file input WITH `capture="environment"` (jumps to
 * the camera app). Declining closes the primer WITHOUT setting primed and
 * opens the SAME input WITHOUT `capture` — the browser's normal file/photo
 * picker — so the flow is never blocked by a decline, only the
 * camera-jump shortcut is gated. Every subsequent tap, once primed, opens
 * the `capture`-attributed input directly with no primer.
 */
export function Dropzone({ onFileSelected }: DropzoneProps) {
  const [primerOpen, setPrimerOpen] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const isOnline = useOnlineStatus();

  const openInput = (withCapture: boolean) => {
    const input = inputRef.current;
    if (!input) return;
    if (withCapture) {
      input.setAttribute("capture", "environment");
    } else {
      input.removeAttribute("capture");
    }
    input.click();
  };

  const handleTap = () => {
    if (!isOnline) return;
    if (isCameraPrimed()) {
      openInput(true);
      return;
    }
    setPrimerOpen(true);
  };

  const handlePrimerContinue = () => {
    setCameraPrimed();
    setPrimerOpen(false);
    openInput(true);
  };

  const handlePrimerDismiss = () => {
    setPrimerOpen(false);
    openInput(false);
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) onFileSelected(file);
    e.target.value = "";
  };

  return (
    <>
      <button
        type="button"
        className={`control ${styles.dropzone}`}
        onClick={handleTap}
        disabled={!isOnline}
      >
        <Camera size={28} strokeWidth={2} aria-hidden="true" className={styles.icon} />
        <span className="textBody">{addItemCopy.upload.placeholder}</span>
      </button>
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        className={styles.hiddenInput}
        aria-hidden="true"
        tabIndex={-1}
        onChange={handleChange}
      />
      <CameraPrimer open={primerOpen} onContinue={handlePrimerContinue} onDismiss={handlePrimerDismiss} />
    </>
  );
}
