"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { Input } from "@/components/ui/Input/Input";
import { Button } from "@/components/ui/Button/Button";
import { Banner } from "@/components/ui/Banner/Banner";
import { createClient } from "@/lib/supabase/client";
import { useValidatedField, validateEmail } from "@/lib/auth-validation";
import { authCopy } from "@/lib/auth-copy";
import styles from "./AuthForm.module.css";

/**
 * spec.md US3 / FR-006. The confirmation state is deliberately identical
 * whether or not the email is registered — Supabase's own
 * resetPasswordForEmail doesn't reveal that either, so this form never has
 * to branch on it. In-place state swap, not a route change.
 */
export function ForgotPasswordForm() {
  const email = useValidatedField(validateEmail);
  const [formError, setFormError] = useState<string | undefined>(undefined);
  const [sent, setSent] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setFormError(undefined);

    const emailError = validateEmail(email.value);
    email.onBlur();
    if (emailError) return;

    setSubmitting(true);
    const supabase = createClient();
    const { error } = await supabase.auth.resetPasswordForEmail(email.value);
    setSubmitting(false);

    if (error) {
      setFormError(authCopy.forgot.error.body);
      return;
    }

    setSent(email.value);
  }

  if (sent) {
    return (
      <div className={styles.form}>
        <p className="textBody">
          Check your inbox: if an account exists for <strong>{sent}</strong>, a reset link is on its way.
        </p>
        <Link href="/signin">{authCopy.forgot.sent.cta}</Link>
      </div>
    );
  }

  return (
    <form className={styles.form} onSubmit={handleSubmit} noValidate>
      {formError && <Banner variant="error">{formError}</Banner>}
      <Input
        type="email"
        label="Email"
        value={email.value}
        onChange={email.onChange}
        onBlur={email.onBlur}
        error={email.error}
      />
      <Button type="submit" width="stretch" state={submitting ? "loading" : "default"}>
        Send reset link
      </Button>
    </form>
  );
}
