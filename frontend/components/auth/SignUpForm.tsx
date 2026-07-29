"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Input } from "@/components/ui/Input/Input";
import { Button } from "@/components/ui/Button/Button";
import { Banner } from "@/components/ui/Banner/Banner";
import { createClient } from "@/lib/supabase/client";
import { useValidatedField, validateEmail, validatePassword, validateConfirmPassword } from "@/lib/auth-validation";
import { authCopy } from "@/lib/auth-copy";
import styles from "./AuthForm.module.css";

/**
 * spec.md US1 (FR-002). Field errors beneath their own field, form-level
 * errors in a Banner above the form (FR-018) — two different mechanisms,
 * per handoff trap #2.
 */
export function SignUpForm() {
  const router = useRouter();
  const email = useValidatedField(validateEmail);
  const password = useValidatedField(validatePassword);
  const confirmPassword = useValidatedField((value) => validateConfirmPassword(password.value, value));
  const [formError, setFormError] = useState<string | undefined>(undefined);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setFormError(undefined);

    const emailError = validateEmail(email.value);
    const passwordError = validatePassword(password.value);
    const confirmError = validateConfirmPassword(password.value, confirmPassword.value);
    email.onBlur();
    password.onBlur();
    confirmPassword.onBlur();
    if (emailError || passwordError || confirmError) return;

    setSubmitting(true);
    const supabase = createClient();
    const { error } = await supabase.auth.signUp({ email: email.value, password: password.value });
    setSubmitting(false);

    if (error) {
      setFormError(authCopy.signup.error.body);
      return;
    }

    router.push("/recommend");
    router.refresh();
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
      <Input
        type="password"
        label="Password"
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
        Create account
      </Button>
      <p className={`textBody ${styles.hint}`}>
        Already have an account? <Link href="/signin">Sign in</Link>
      </p>
    </form>
  );
}
