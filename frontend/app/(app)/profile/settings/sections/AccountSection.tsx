"use client";

import { useEffect, useState } from "react";
import { Input } from "@/components/ui/Input/Input";
import { Button } from "@/components/ui/Button/Button";
import { createClient } from "@/lib/supabase/client";
import styles from "./sections.module.css";

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

interface Props {
  disabled: boolean;
}

/**
 * design-system.md §4 Account. The email edit calls Supabase Auth's own
 * `updateUser` directly — no backend route, no user_profile column, per
 * specs/013-profile-settings/research.md §3 (identity stays Auth's data,
 * declared taste stays this feature's table).
 */
export function AccountSection({ disabled }: Props) {
  const [email, setEmail] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | undefined>(undefined);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const supabase = createClient();
    supabase.auth.getSession().then(({ data }) => setEmail(data.session?.user.email ?? null));
  }, []);

  function startEdit() {
    setDraft(email ?? "");
    setError(undefined);
    setEditing(true);
  }

  function validate() {
    if (!EMAIL_PATTERN.test(draft)) {
      setError("Enter a valid email address.");
      return false;
    }
    setError(undefined);
    return true;
  }

  async function done() {
    if (!validate()) return;
    setSaving(true);
    try {
      const supabase = createClient();
      const { error: updateError } = await supabase.auth.updateUser({ email: draft });
      if (updateError) {
        setError("That didn't save. Check your connection and try again.");
        return;
      }
      setEmail(draft);
      setEditing(false);
    } finally {
      setSaving(false);
    }
  }

  return (
    <section>
      <div className={styles.header}>
        <h2 className="textSectionTitle">Account</h2>
      </div>

      <div className={styles.field}>
        {editing ? (
          <Input
            type="email"
            label="Email"
            value={draft}
            onChange={setDraft}
            onBlur={validate}
            error={error}
            disabled={disabled}
          />
        ) : (
          <>
            <p className={`textLabel ${styles.fieldLabel}`}>Email</p>
            <p className="textBody">{email ?? "—"}</p>
          </>
        )}
      </div>

      <Button variant="secondary" width="stretch" disabled={disabled || saving} onClick={editing ? done : startEdit}>
        {editing ? "Done" : "Edit"}
      </Button>
    </section>
  );
}
