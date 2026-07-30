"use client";

import { useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import { Input } from "@/components/ui/Input/Input";
import { Button } from "@/components/ui/Button/Button";
import { Banner } from "@/components/ui/Banner/Banner";
import { createClient } from "@/lib/supabase/client";
import { useValidatedField, validatePassword, validateConfirmPassword } from "@/lib/auth-validation";
import { authCopy } from "@/lib/auth-copy";
import styles from "./AuthForm.module.css";

interface ResetPasswordFormProps {
  token: string;
}

type Stage = "verifying" | "form" | "error" | "success";

/**
 * spec.md US3 (FR-007/FR-008). Three states per design-system.md §4:
 * form/error/success. `token` is Supabase's `{{ .TokenHash }}` recovery
 * value (specs/003-auth/research.md §6), verified via `verifyOtp` on mount
 * to establish a short-lived recovery session — explicitly signed out
 * again after a successful password update so nothing crosses into an
 * authenticated app session (design-decisions §12's "do not auto-sign-in").
 */
export function ResetPasswordForm({ token }: ResetPasswordFormProps) {
  const [stage, setStage] = useState<Stage>("verifying");
  const [formError, setFormError] = useState<string | undefined>(undefined);
  const [submitting, setSubmitting] = useState(false);
  const password = useValidatedField(validatePassword);
  const confirmPassword = useValidatedField((value) => validateConfirmPassword(password.value, value));

  useEffect(() => {
    let cancelled = false;
    async function verify() {
      const supabase = createClient();
      const { error } = await supabase.auth.verifyOtp({ token_hash: token, type: "recovery" });
      if (!cancelled) setStage(error ? "error" : "form");
    }
    verify();
    return () => {
      cancelled = true;
    };
  }, [token]);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setFormError(undefined);

    const passwordError = validatePassword(password.value);
    const confirmError = validateConfirmPassword(password.value, confirmPassword.value);
    password.onBlur();
    confirmPassword.onBlur();
    if (passwordError || confirmError) return;

    setSubmitting(true);
    const supabase = createClient();
    const { error } = await supabase.auth.updateUser({ password: password.value });
    if (!error) {
      await supabase.auth.signOut();
    }
    setSubmitting(false);

    if (error) {
      setFormError(authCopy.reset.error.body);
      return;
    }

    setStage("success");
  }

  if (stage === "verifying") {
    return <p className="textBody">Checking your link…</p>;
  }

  if (stage === "error") {
    return (
      <div className={styles.form}>
        <p className="textBody">{authCopy.reset.error.body}</p>
        <Link href="/forgot-password">{authCopy.reset.error.cta}</Link>
      </div>
    );
  }

  if (stage === "success") {
    return (
      <div className={styles.form}>
        <p className="textBody">{authCopy.reset.success.body}</p>
        <Link href="/signin">{authCopy.reset.success.cta}</Link>
      </div>
    );
  }

  return (
    <form className={styles.form} onSubmit={handleSubmit} noValidate>
      {formError && <Banner variant="error">{formError}</Banner>}
      <Input
        type="password"
        label="New password"
        value={password.value}
        onChange={password.onChange}
        onBlur={password.onBlur}
        error={password.error}
      />
      <Input
        type="password"
        label="Confirm password"
        value={confirmPassword.value}
        onChange={confirmPassword.onChange}
        onBlur={confirmPassword.onBlur}
        error={confirmPassword.error}
      />
      <Button type="submit" width="stretch" state={submitting ? "loading" : "default"}>
        Update password
      </Button>
    </form>
  );
}
