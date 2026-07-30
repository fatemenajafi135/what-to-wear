"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Input } from "@/components/ui/Input/Input";
import { Button } from "@/components/ui/Button/Button";
import { Banner } from "@/components/ui/Banner/Banner";
import { GoogleButton } from "@/components/auth/GoogleButton";
import { createClient } from "@/lib/supabase/client";
import { useGoogleAuthAvailable } from "@/lib/supabase/useGoogleAuthAvailable";
import { useValidatedField, validateEmail, validatePassword } from "@/lib/auth-validation";
import { authCopy } from "@/lib/auth-copy";
import styles from "./AuthForm.module.css";

/**
 * spec.md US2 (FR-003). Deliberately doesn't distinguish "no such email"
 * from "wrong password" in its error copy — auth.signin.error.body reads
 * the same either way, so this never has to make that distinction itself.
 */
export function SignInForm() {
  const router = useRouter();
  const email = useValidatedField(validateEmail);
  const password = useValidatedField(validatePassword);
  const [formError, setFormError] = useState<string | undefined>(undefined);
  const [submitting, setSubmitting] = useState(false);
  const googleAvailable = useGoogleAuthAvailable();

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setFormError(undefined);

    const emailError = validateEmail(email.value);
    const passwordError = validatePassword(password.value);
    email.onBlur();
    password.onBlur();
    if (emailError || passwordError) return;

    setSubmitting(true);
    const supabase = createClient();
    const { error } = await supabase.auth.signInWithPassword({ email: email.value, password: password.value });
    setSubmitting(false);

    if (error) {
      setFormError(authCopy.signin.error.body);
      return;
    }

    router.push("/recommend");
    router.refresh();
  }

  function handleGoogleClick() {
    const supabase = createClient();
    supabase.auth.signInWithOAuth({
      provider: "google",
      options: { redirectTo: `${window.location.origin}/auth/callback` },
    });
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
      <div>
        <Input
          type="password"
          label="Password"
          value={password.value}
          onChange={password.onChange}
          onBlur={password.onBlur}
          error={password.error}
        />
        <p className={`textCaption ${styles.forgotLink}`}>
          <Link href="/forgot-password">Forgot password?</Link>
        </p>
      </div>
      <Button type="submit" width="stretch" state={submitting ? "loading" : "default"}>
        Sign in
      </Button>
      <GoogleButton onClick={handleGoogleClick} disabled={!googleAvailable} />
      <p className={`textBody ${styles.hint}`}>
        Don&apos;t have an account? <Link href="/signup">Sign up</Link>
      </p>
    </form>
  );
}
