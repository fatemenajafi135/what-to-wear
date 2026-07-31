"use client";

import { useState } from "react";
import { Chip } from "@/components/ui/Chip/Chip";
import { TagInput } from "@/components/ui/TagInput/TagInput";
import { Button } from "@/components/ui/Button/Button";
import { updateStylePreferences, type ProfileResponse } from "@/lib/api/profile";
import styles from "./sections.module.css";

const STYLE_TAGS = ["Classic", "Minimal", "Bold", "Casual", "Edgy"];
const COLOUR_TAGS = ["Neutral tones", "Jewel tones", "Pastels", "Monochrome", "Earth tones"];

interface Props {
  profile: ProfileResponse;
  disabled: boolean;
  onSaved: (profile: ProfileResponse) => void;
}

function toggle(list: string[], value: string): string[] {
  return list.includes(value) ? list.filter((v) => v !== value) : [...list, value];
}

/**
 * design-system.md §4 Style preferences: style tags + colour tags
 * (multi-select Chip) and brands-to-avoid (TagInput). Edit/Done is a draft
 * commit — navigating away without Done discards local state (FR-011),
 * since nothing here is written until "Done" calls the API.
 */
export function StylePreferencesSection({ profile, disabled, onSaved }: Props) {
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [styleTags, setStyleTags] = useState<string[]>(profile.style_tags ?? []);
  const [colourTags, setColourTags] = useState<string[]>(profile.colour_tags ?? []);
  const [brandsToAvoid, setBrandsToAvoid] = useState<string[]>(profile.brands_to_avoid ?? []);

  function startEdit() {
    setStyleTags(profile.style_tags ?? []);
    setColourTags(profile.colour_tags ?? []);
    setBrandsToAvoid(profile.brands_to_avoid ?? []);
    setEditing(true);
  }

  async function done() {
    setSaving(true);
    try {
      const updated = await updateStylePreferences({
        style_tags: styleTags,
        colour_tags: colourTags,
        brands_to_avoid: brandsToAvoid,
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
        <h2 className="textSectionTitle">Style preferences</h2>
        <Button
          variant="secondary"
          width="intrinsic"
          disabled={disabled || saving}
          onClick={editing ? done : startEdit}
        >
          {editing ? "Done" : "Edit"}
        </Button>
      </div>

      <div className={styles.field}>
        <p className={`textLabel ${styles.fieldLabel}`}>Fit &amp; style</p>
        {editing ? (
          <div className={styles.chipRow}>
            {STYLE_TAGS.map((tag) => (
              <Chip
                key={tag}
                active={styleTags.includes(tag)}
                disabled={disabled}
                onClick={() => setStyleTags(toggle(styleTags, tag))}
              >
                {tag}
              </Chip>
            ))}
          </div>
        ) : (
          <p className="textBody">{styleTags.length > 0 ? styleTags.join(", ") : "None selected"}</p>
        )}
      </div>

      <div className={styles.field}>
        <p className={`textLabel ${styles.fieldLabel}`}>Colour palettes</p>
        {editing ? (
          <div className={styles.chipRow}>
            {COLOUR_TAGS.map((tag) => (
              <Chip
                key={tag}
                active={colourTags.includes(tag)}
                disabled={disabled}
                onClick={() => setColourTags(toggle(colourTags, tag))}
              >
                {tag}
              </Chip>
            ))}
          </div>
        ) : (
          <p className="textBody">{colourTags.length > 0 ? colourTags.join(", ") : "None selected"}</p>
        )}
      </div>

      <div className={styles.field}>
        {editing ? (
          <TagInput
            label="Brands to avoid"
            values={brandsToAvoid}
            onChange={setBrandsToAvoid}
            placeholder="Type a brand, press Enter"
            disabled={disabled}
          />
        ) : (
          <>
            <p className={`textLabel ${styles.fieldLabel}`}>Brands to avoid</p>
            <p className="textBody">{brandsToAvoid.length > 0 ? brandsToAvoid.join(", ") : "None"}</p>
          </>
        )}
      </div>
    </section>
  );
}
