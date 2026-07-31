"use client";

import { useState } from "react";
import { Chip } from "@/components/ui/Chip/Chip";
import { DatePicker } from "@/components/ui/DatePicker/DatePicker";
import { Select, type SelectOption } from "@/components/ui/Select/Select";
import { Button } from "@/components/ui/Button/Button";
import { BodyShapePicker, BodyShapeGlyph, BODY_SHAPE_OPTIONS, type BodyShape } from "@/components/ui/BodyShapePicker/BodyShapePicker";
import { updateBodySize, type ProfileResponse } from "@/lib/api/profile";
import styles from "./sections.module.css";

const GENDERS: { value: string; label: string }[] = [
  { value: "woman", label: "Woman" },
  { value: "man", label: "Man" },
  { value: "non_binary", label: "Non-binary" },
  { value: "prefer_not_to_say", label: "Prefer not to say" },
];

const TOP_SIZES = ["XXS", "XS", "S", "M", "L", "XL", "XXL", "XXXL"];
const BOTTOM_SIZES = Array.from({ length: 11 }, (_, i) => String(i * 2).padStart(2, "0"));

// Not specified anywhere in spec/plan/data-model (only Top/Bottom size are
// pinned there) — this task's own reasonable choice, recorded here rather
// than left silently undefined. See specs/013-profile-settings/tasks.md T021.
const HEIGHT_OPTIONS = (() => {
  const options: string[] = [];
  for (let totalInches = 58; totalInches <= 78; totalInches++) {
    const feet = Math.floor(totalInches / 12);
    const inches = totalInches % 12;
    options.push(`${feet} ft ${inches} in`);
  }
  return options;
})();

const SHOE_SIZE_OPTIONS = (() => {
  const options: string[] = [];
  for (let half = 10; half <= 26; half++) {
    options.push(half % 2 === 0 ? String(half / 2) : `${Math.floor(half / 2)}.5`);
  }
  return options;
})();

function toSelectOptions(values: string[]): SelectOption[] {
  return [{ value: "", label: "Not set" }, ...values.map((v) => ({ value: v, label: v }))];
}

const BODY_SHAPE_LABELS: Record<string, string> = Object.fromEntries(
  BODY_SHAPE_OPTIONS.map((o) => [o.value, o.label]),
);
const GENDER_LABELS: Record<string, string> = Object.fromEntries(GENDERS.map((g) => [g.value, g.label]));

interface Props {
  profile: ProfileResponse;
  disabled: boolean;
  onSaved: (profile: ProfileResponse) => void;
}

interface Draft {
  bodyShape: BodyShape | null;
  gender: string | null;
  birthDate: string;
  height: string;
  topSize: string;
  bottomSize: string;
  shoeSize: string;
}

function draftFromProfile(profile: ProfileResponse): Draft {
  return {
    bodyShape: (profile.body_shape as BodyShape | null) ?? null,
    gender: profile.gender ?? null,
    birthDate: profile.birth_date ?? "",
    height: profile.height ?? "",
    topSize: profile.top_size ?? "",
    bottomSize: profile.bottom_size ?? "",
    shoeSize: profile.shoe_size ?? "",
  };
}

/**
 * design-system.md §4 Body & size. Body shape is a single-select illustrated
 * picker (FR-005), Gender a single-select Chip row, Birth date a DatePicker
 * validated against "not in the future" (spec.md User Story 3, scenario 3),
 * and four native Selects. Edit/Done draft-commit, same as Style preferences.
 */
export function BodySizeSection({ profile, disabled, onSaved }: Props) {
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [draft, setDraft] = useState<Draft>(() => draftFromProfile(profile));
  const [birthDateError, setBirthDateError] = useState<string | undefined>(undefined);

  function startEdit() {
    setDraft(draftFromProfile(profile));
    setBirthDateError(undefined);
    setEditing(true);
  }

  function updateBirthDate(value: string) {
    setDraft((d) => ({ ...d, birthDate: value }));
    if (value && value > new Date().toISOString().slice(0, 10)) {
      setBirthDateError("Enter a date in the past.");
    } else {
      setBirthDateError(undefined);
    }
  }

  async function done() {
    if (birthDateError) return;
    setSaving(true);
    try {
      const updated = await updateBodySize({
        body_shape: draft.bodyShape,
        gender: draft.gender,
        birth_date: draft.birthDate || null,
        height: draft.height || null,
        top_size: draft.topSize || null,
        bottom_size: draft.bottomSize || null,
        shoe_size: draft.shoeSize || null,
      });
      onSaved(updated);
      setEditing(false);
    } finally {
      setSaving(false);
    }
  }

  return (
    <section>
      <div className={styles.header}>
        <h2 className="textSectionTitle">Body &amp; size</h2>
        <Button
          variant="secondary"
          width="intrinsic"
          disabled={disabled || saving || Boolean(birthDateError)}
          onClick={editing ? done : startEdit}
        >
          {editing ? "Done" : "Edit"}
        </Button>
      </div>

      <div className={styles.field}>
        <p className={`textLabel ${styles.fieldLabel}`}>Body shape</p>
        {editing ? (
          <BodyShapePicker
            value={draft.bodyShape}
            onChange={(value) => setDraft((d) => ({ ...d, bodyShape: value }))}
            disabled={disabled}
          />
        ) : draft.bodyShape ? (
          <div className={styles.chipRowCentered}>
            <BodyShapeGlyph shape={draft.bodyShape} />
            <p className="textBody">{BODY_SHAPE_LABELS[draft.bodyShape]}</p>
          </div>
        ) : (
          <p className="textBody">Not set yet</p>
        )}
      </div>

      <div className={styles.field}>
        <p className={`textLabel ${styles.fieldLabel}`}>Gender</p>
        {editing ? (
          <div className={styles.chipRow}>
            {GENDERS.map((g) => (
              <Chip
                key={g.value}
                active={draft.gender === g.value}
                disabled={disabled}
                onClick={() => setDraft((d) => ({ ...d, gender: g.value }))}
              >
                {g.label}
              </Chip>
            ))}
          </div>
        ) : (
          <p className="textBody">{draft.gender ? GENDER_LABELS[draft.gender] : "Not set yet"}</p>
        )}
      </div>

      <div className={styles.field}>
        {editing ? (
          <DatePicker
            label="Birth date"
            value={draft.birthDate}
            onChange={updateBirthDate}
            error={birthDateError}
            disabled={disabled}
          />
        ) : (
          <>
            <p className={`textLabel ${styles.fieldLabel}`}>Date of birth</p>
            <p className="textBody">
              {draft.birthDate
                ? new Date(`${draft.birthDate}T00:00:00`).toLocaleDateString(undefined, {
                    year: "numeric",
                    month: "long",
                    day: "numeric",
                  })
                : "Not set yet"}
            </p>
          </>
        )}
      </div>

      <div className={styles.fieldGrid}>
        {editing ? (
          <>
            <Select
              label="Height"
              value={draft.height}
              onChange={(v) => setDraft((d) => ({ ...d, height: v }))}
              options={toSelectOptions(HEIGHT_OPTIONS)}
              disabled={disabled}
            />
            <Select
              label="Shoe size"
              value={draft.shoeSize}
              onChange={(v) => setDraft((d) => ({ ...d, shoeSize: v }))}
              options={toSelectOptions(SHOE_SIZE_OPTIONS)}
              disabled={disabled}
            />
            <Select
              label="Top size"
              value={draft.topSize}
              onChange={(v) => setDraft((d) => ({ ...d, topSize: v }))}
              options={toSelectOptions(TOP_SIZES)}
              disabled={disabled}
            />
            <Select
              label="Bottom size"
              value={draft.bottomSize}
              onChange={(v) => setDraft((d) => ({ ...d, bottomSize: v }))}
              options={toSelectOptions(BOTTOM_SIZES)}
              disabled={disabled}
            />
          </>
        ) : (
          <>
            <div>
              <p className={`textLabel ${styles.fieldLabel}`}>Height</p>
              <p className="textBody">{draft.height || "Not set yet"}</p>
            </div>
            <div>
              <p className={`textLabel ${styles.fieldLabel}`}>Shoe size</p>
              <p className="textBody">{draft.shoeSize || "Not set yet"}</p>
            </div>
            <div>
              <p className={`textLabel ${styles.fieldLabel}`}>Top size</p>
              <p className="textBody">{draft.topSize || "Not set yet"}</p>
            </div>
            <div>
              <p className={`textLabel ${styles.fieldLabel}`}>Bottom size</p>
              <p className="textBody">{draft.bottomSize || "Not set yet"}</p>
            </div>
          </>
        )}
      </div>
    </section>
  );
}
