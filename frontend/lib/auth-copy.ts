/**
 * design/design-system.md §6 "Auth" copy table — verbatim, shipped as-is
 * pending localization (§9). `auth.forgot.sent.body` isn't here: it embeds
 * a bold `{email}` interpolation and is rendered directly as JSX in
 * ForgotPasswordForm rather than templated as a string.
 */
export const authCopy = {
  signin: {
    error: {
      body: "That email and password don't match. Try again or reset your password.",
    },
  },
  signup: {
    error: {
      body: "We couldn't complete your sign-up with those details. Check them and try again, or sign in below.",
    },
  },
  forgot: {
    error: {
      body: "Something went wrong sending that email. Try again in a moment.",
    },
    sent: {
      cta: "Back to sign in",
    },
  },
  reset: {
    error: {
      body: "This link has expired. Request a new one.",
      cta: "Resend link",
    },
    success: {
      body: "Your password has been updated.",
      cta: "Sign in",
    },
  },
} as const;
